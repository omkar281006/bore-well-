# BoreWise ESP32 firmware

`main.cpp` sends schema v2 telemetry (see `docs/telemetry-schema.md`) to the BoreWise API.

## Flash it

1. Install [PlatformIO](https://platformio.org/) or the Arduino IDE with ESP32 board support.
2. Install `ArduinoJson` (6.x or 7.x). For a DS18B20 also install `OneWire` and `DallasTemperature`, then set `USE_DS18B20 1`.
3. In `main.cpp` set `WIFI_SSID`, `WIFI_PASSWORD`, `WELL_ID` and `API_BASE`:
   - AWS: the `ApiUrl` output of `sam deploy`
   - local: `http://<your-laptop-ip>:8000` while `python backend/app.py` runs (same Wi-Fi)
4. Board `ESP32 Dev Module`, 115200 baud.

## Wiring

| Part | ESP32 pin | Note |
|---|---|---|
| SCT-013-030 current clamp | GPIO 34 | 3.5 mm jack to a 1.65 V bias divider; one live wire through the clamp |
| DS18B20 (optional) | GPIO 4 | 4.7 kΩ pull-up to 3.3 V |
| INMP441 mic + MAX98357A amp | I2S (to be added) | for the acoustic sounder, `DEPTH_SOURCE 1` |

## What it sends

- a heartbeat every 15 minutes
- an event the moment the pump starts or stops (detected from motor current)
- a reading every 2 minutes for the first hour after the pump stops; the backend fits the refill curve to these
- no depth while the pump runs (`depth_to_water_m: null`, `measurement_valid: false`)
- timestamps from NTP in IST; records are buffered and sent to `/telemetry/batch`, so Wi-Fi drops lose nothing

## Honest labelling

Until the acoustic sounder is built, `DEPTH_SOURCE 0` produces a simulated refill curve and every record says
`"data_source": "simulated"`. Switch to `1` and the label becomes `bench-tested`; use `field-measured` only for a
real borewell. The earlier firmware sent a fake depth sweep marked as bench-tested and a fixed timestamp; both are fixed.

Acoustic ranging limits (signal loss over 50–150 m of narrow tube, joint echoes, pump noise, temperature) are covered in
`docs/limitations.md` and the research report. The sounder must use a low 60–250 Hz chirp; an ultrasonic module such as
the JSN-SR04T reaches only ~4.5 m and cannot measure a borewell.
