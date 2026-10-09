/*
 * BoreWise ESP32 Bench Telemetry Firmware
 * 
 * Target Board: ESP32 Dev Module
 * Framework: Arduino C++
 * Purpose: Transmit bench-tested / simulated sensor telemetry to AWS API Endpoint
 * 
 * Required Libraries:
 * - WiFi.h (Built-in ESP32)
 * - HTTPClient.h (Built-in ESP32)
 * - ArduinoJson (v6.x)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- Configuration ---
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// AWS API Gateway or Lambda Function URL Endpoint
const char* API_ENDPOINT = "https://your-api-id.lambda-url.us-east-1.on.aws/telemetry";

const char* WELL_ID = "BW-001";
const char* DATA_SOURCE = "bench-tested";

// Simulated/Sensored pin definitions
const int PUMP_CURRENT_PIN = 34; // ADC pin for current transformer sensor
const int TEMP_SENSOR_PIN = 35;  // Temperature sensor input

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi Connected successfully!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWi-Fi Connection Failed. Will retry next cycle.");
  }
}

float readSimulatedDepth() {
  // Reads acoustic/bench proximity or generates bench test sweep (40.0m - 52.0m)
  static float depth = 40.0;
  static bool going_down = true;
  if (going_down) {
    depth += 0.2;
    if (depth >= 52.0) going_down = false;
  } else {
    depth -= 0.15;
    if (depth <= 40.0) going_down = true;
  }
  return depth;
}

void sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return;
  }

  HTTPClient http;
  http.begin(API_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  // Construct JSON Payload according to BoreWise Shared Telemetry Schema
  StaticJsonDocument<300> doc;
  doc["well_id"] = WELL_ID;
  
  // ISO8601 Timestamp representation
  doc["timestamp"] = "2026-10-10T09:00:00Z"; 
  doc["data_source"] = DATA_SOURCE;
  doc["depth_to_water_m"] = readSimulatedDepth();
  doc["temperature_c"] = 28.5;
  doc["pump_state"] = (analogRead(PUMP_CURRENT_PIN) > 500) ? "ON" : "OFF";
  doc["pump_run_minutes"] = 15;
  doc["measurement_valid"] = true;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.println("Sending Payload:");
  Serial.println(jsonPayload);

  int httpResponseCode = http.POST(jsonPayload);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("HTTP Response Code: %d\n", httpResponseCode);
    Serial.println("Response: " + response);
  } else {
    Serial.printf("HTTP Error Code: %s\n", http.errorToString(httpResponseCode).c_str());
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== BoreWise ESP32 Telemetry Module Initialized ===");
  connectWiFi();
}

void loop() {
  sendTelemetry();
  // Transmit telemetry record every 60 seconds
  delay(60000);
}
