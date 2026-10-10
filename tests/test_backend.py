"""API, schema and storage tests (no AWS needed: the in-memory store is used)."""

import json

from backend.app import handle_telemetry_get, handle_telemetry_post, lambda_handler
from backend.schema import normalize_record, validate_telemetry_payload, validate_well_config
from backend.storage import MemoryStore, reset_store

VALID = {
    "well_id": "BW-001",
    "timestamp": "2026-10-10T09:00:00Z",
    "data_source": "simulated",
    "depth_to_water_m": 48.2,
    "temperature_c": 28.5,
    "pump_state": "OFF",
    "pump_run_minutes": 42,
    "measurement_valid": True,
}


def setup_function():
    reset_store(MemoryStore())


def test_schema_validation_valid():
    assert validate_telemetry_payload(VALID) == (True, "")
    v2 = {**VALID, "pump_current_a": 5.4, "echo_tau_ms": 281.5, "event": "pump_off", "fw": "0.4.0"}
    assert validate_telemetry_payload(v2) == (True, "")


def test_schema_validation_invalid_depth():
    ok, err = validate_telemetry_payload({**VALID, "depth_to_water_m": 999.0})
    assert not ok and "out of physical bounds" in err


def test_schema_validation_missing_field():
    ok, err = validate_telemetry_payload({"well_id": "BW-001", "timestamp": "2026-10-10T09:00:00Z"})
    assert not ok and "Missing required field" in err


def test_schema_gated_depth():
    pumping = {**VALID, "pump_state": "ON", "depth_to_water_m": None, "measurement_valid": False}
    assert validate_telemetry_payload(pumping)[0]
    assert not validate_telemetry_payload({**pumping, "measurement_valid": True})[0]
    assert not validate_telemetry_payload({**VALID, "timestamp": "2026-10-10T09:00:00"})[0]  # no timezone
    assert not validate_telemetry_payload({**VALID, "event": "explode"})[0]


def test_timestamps_normalised_to_utc():
    rec = normalize_record({**VALID, "timestamp": "2026-10-10T14:30:00+05:30"})
    assert rec["timestamp"] == "2026-10-10T09:00:00Z"


def test_well_config_validation():
    assert validate_well_config({"well_id": "BW-9", "depth_m": 120, "intake_m": 103})[0]
    assert not validate_well_config({"well_id": "BW-9", "depth_m": 100, "intake_m": 120})[0]
    assert not validate_well_config({"well_id": "BW-9", "bore_type": "rocket"})[0]


def test_lambda_handler_post_and_get():
    post = {"httpMethod": "POST", "path": "/telemetry", "body": json.dumps({**VALID, "well_id": "BW-TEST"})}
    res = lambda_handler(post, None)
    assert res["statusCode"] == 201
    assert json.loads(res["body"])["status"] == "success"

    get = {"httpMethod": "GET", "path": "/telemetry", "queryStringParameters": {"well_id": "BW-TEST"}}
    res = lambda_handler(get, None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200 and body["count"] >= 1


def test_http_api_v2_events_and_batch():
    batch = {"records": [VALID, {**VALID, "timestamp": "2026-10-10T09:15:00Z"}, {**VALID, "depth_to_water_m": -5}]}
    event = {"rawPath": "/telemetry/batch", "requestContext": {"http": {"method": "POST"}}, "body": json.dumps(batch)}
    res = lambda_handler(event, None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 207 and body["accepted"] == 2 and body["rejected_count"] == 1
    assert handle_telemetry_get("BW-001")[1]["count"] == 2


def test_unknown_route_and_bad_json():
    assert lambda_handler({"httpMethod": "GET", "path": "/nope"}, None)["statusCode"] == 404
    assert lambda_handler({"httpMethod": "POST", "path": "/telemetry", "body": "{oops"}, None)["statusCode"] == 400


def test_handle_post_rejects_invalid():
    status, body = handle_telemetry_post({**VALID, "pump_state": "MAYBE"})
    assert status == 400 and "pump_state" in body["error"]
