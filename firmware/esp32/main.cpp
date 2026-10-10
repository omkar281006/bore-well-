/*
 * BoreWise ESP32 telemetry firmware (schema v2)
 *
 * Board: ESP32 Dev Module, Arduino framework. Libraries: ArduinoJson 6.x or 7.x,
 * OneWire + DallasTemperature (only if USE_DS18B20 is 1).
 *
 * What it does, matching docs/telemetry-schema.md:
 *  - real timestamps from NTP (IST offset), never a fixed string
 *  - pump state from an SCT-013 current clamp (true RMS over 200 ms), plus pump_current_a
 *  - depth sounding is gated: no depth while the pump runs (measurement_valid = false)
 *  - heartbeat every 15 min; an event record when the pump starts or stops;
 *    a reading every 2 min for the first hour of refill (this feeds the recovery fit)
 *  - records are buffered and sent in batches to POST /telemetry/batch, so a Wi-Fi drop loses nothing
 *  - data_source is "simulated" until a real depth sensor is fitted (DEPTH_SOURCE below);
 *    the old firmware labelled a fake depth sweep as "bench-tested"
 *
 * Acoustic sounding (60-250 Hz chirp + cross-correlation, see docs/research) is not implemented yet:
 * soundDepthMetres() is the single place to add it.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <math.h>

// ----------------------------------------------------------------- configuration
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
// API base URL: the SAM output ApiUrl, or http://<laptop-ip>:8000 for the local Python API
const char* API_BASE = "https://your-api-id.execute-api.ap-south-1.amazonaws.com";
const char* WELL_ID = "BW-001";
const char* FW_VERSION = "0.4.0";

// Depth source: 0 = simulated sweep (labelled "simulated"), 1 = acoustic sounder (labelled "bench-tested")
#define DEPTH_SOURCE 0
#define USE_DS18B20 0

const int PUMP_CURRENT_PIN = 34;        // SCT-013-030 (1 V = 30 A) via burden + 1.65 V bias into ADC
const float CLAMP_AMPS_PER_VOLT = 30.0;
const float PUMP_ON_AMPS = 1.0;         // above this the pump is running
const int TEMP_PIN = 4;                 // DS18B20 data pin

const uint32_t HEARTBEAT_MS = 15UL * 60UL * 1000UL;
const uint32_t REFILL_EVERY_MS = 2UL * 60UL * 1000UL;
const uint32_t REFILL_WINDOW_MS = 60UL * 60UL * 1000UL;
const uint32_t SAMPLE_MS = 5000;        // how often the pump current is checked
const size_t MAX_BUFFER = 40;           // records kept while offline

#if USE_DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);
#endif

// ----------------------------------------------------------------- state
String buffer[MAX_BUFFER];
size_t buffered = 0;
bool pumpOn = false;
uint32_t pumpOnSince = 0, lastOff = 0, lastHeartbeat = 0, lastRefill = 0, lastSample = 0;
bool refilling = false;

// ----------------------------------------------------------------- sensors
float readPumpCurrentRms() {
  // True RMS over 200 ms (10 mains cycles at 50 Hz), bias removed.
  const int n = 400;
  double sum = 0, sumSq = 0;
  for (int i = 0; i < n; i++) {
    double v = analogReadMilliVolts(PUMP_CURRENT_PIN) / 1000.0;
    sum += v;
    sumSq += v * v;
    delayMicroseconds(500);
  }
  double mean = sum / n;
  double var = sumSq / n - mean * mean;
  return var > 0 ? sqrt(var) * CLAMP_AMPS_PER_VOLT : 0.0;
}

float readTemperatureC() {
#if USE_DS18B20
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  if (t > -50 && t < 85) return t;
#endif
  return 27.5;  // no sensor fitted: the backend treats this as a nominal value
}

float soundDepthMetres(float tempC, float* tauMs) {
#if DEPTH_SOURCE == 1
  // TODO: emit a 60-250 Hz log chirp on the MAX98357A (I2S), record the INMP441 (I2S),
  // cross-correlate, apply a tube-loss gain, take the strongest echo after 4 m and refine it
  // with parabolic interpolation. c = (331.3 + 0.606*T) * (1 - 0.0082) for a 25 mm tube.
  *tauMs = NAN;
  return NAN;
#else
  // Simulated level: slow seasonal decline plus refill after each run. Labelled "simulated".
  static float level = 40.0;
  float since = (millis() - lastOff) / 3600000.0;   // hours since pump stopped
  float d = level + 6.0 * expf(-since / 0.6);         // refill curve
  level += 0.0005;                                    // seasonal decline per reading
  float c = (331.3 + 0.606 * tempC) * (1 - 0.0082);
  *tauMs = 2.0 * d / c * 1000.0;
  return d;
#endif
}

// ----------------------------------------------------------------- time
void startClock() {
  configTime(19800, 0, "pool.ntp.org", "time.google.com");  // IST = UTC+5:30
  struct tm tm;
  for (int i = 0; i < 20 && !getLocalTime(&tm, 500); i++) {}
}

bool isoNow(char* out, size_t len) {
  struct tm tm;
  if (!getLocalTime(&tm, 200)) return false;
  strftime(out, len, "%Y-%m-%dT%H:%M:%S+05:30", &tm);
  return true;
}

// ----------------------------------------------------------------- records
void queueRecord(const char* event) {
  char ts[32];
  if (!isoNow(ts, sizeof ts)) {
    Serial.println("No NTP time yet; skipping record");
    return;
  }
  float tempC = readTemperatureC();
  float amps = readPumpCurrentRms();
  StaticJsonDocument<512> doc;
  doc["well_id"] = WELL_ID;
  doc["timestamp"] = ts;
  doc["data_source"] = DEPTH_SOURCE == 1 ? "bench-tested" : "simulated";
  doc["temperature_c"] = tempC;
  doc["pump_state"] = pumpOn ? "ON" : "OFF";
  doc["pump_run_minutes"] = pumpOn ? (millis() - pumpOnSince) / 60000.0 : 0;
  doc["pump_current_a"] = amps;
  doc["fw"] = FW_VERSION;
  if (event) doc["event"] = event;

  float tau = NAN;
  float depth = pumpOn ? NAN : soundDepthMetres(tempC, &tau);   // sounding is gated while pumping
  bool valid = !isnan(depth);
  if (valid) doc["depth_to_water_m"] = depth; else doc["depth_to_water_m"] = nullptr;
  if (!isnan(tau)) doc["echo_tau_ms"] = tau; else doc["echo_tau_ms"] = nullptr;
  doc["measurement_valid"] = valid;

  String json;
  serializeJson(doc, json);
  if (buffered == MAX_BUFFER) {             // drop the oldest when offline too long
    for (size_t i = 1; i < MAX_BUFFER; i++) buffer[i - 1] = buffer[i];
    buffered--;
  }
  buffer[buffered++] = json;
  Serial.println(json);
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  return WiFi.status() == WL_CONNECTED;
}

void flush() {
  if (!buffered || !ensureWiFi()) return;
  String body = "{\"records\":[";
  for (size_t i = 0; i < buffered; i++) {
    if (i) body += ",";
    body += buffer[i];
  }
  body += "]}";
  HTTPClient http;
  http.begin(String(API_BASE) + "/telemetry/batch");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  Serial.printf("POST /telemetry/batch -> %d\n", code);
  if (code == 201 || code == 207) buffered = 0;   // 207: some rejected; they will not pass on retry either
  http.end();
}

// ----------------------------------------------------------------- main loop
void setup() {
  Serial.begin(115200);
  analogSetPinAttenuation(PUMP_CURRENT_PIN, ADC_11db);
#if USE_DS18B20
  tempSensor.begin();
#endif
  ensureWiFi();
  startClock();
  lastHeartbeat = millis() - HEARTBEAT_MS;  // send one reading straight away
  Serial.println("BoreWise telemetry module ready");
}

void loop() {
  uint32_t now = millis();
  if (now - lastSample >= SAMPLE_MS) {
    lastSample = now;
    bool on = readPumpCurrentRms() > PUMP_ON_AMPS;
    if (on && !pumpOn) {
      pumpOn = true;
      pumpOnSince = now;
      refilling = false;
      queueRecord("pump_on");
      flush();
    } else if (!on && pumpOn) {
      pumpOn = false;
      lastOff = now;
      refilling = true;
      lastRefill = now;
      queueRecord("pump_off");
      flush();
    }
  }
  if (refilling && now - lastRefill >= REFILL_EVERY_MS) {
    lastRefill = now;
    queueRecord(nullptr);
    if (now - lastOff >= REFILL_WINDOW_MS) refilling = false;
    if (buffered >= 10) flush();
  }
  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    queueRecord(nullptr);
    flush();
  }
  delay(50);
}
