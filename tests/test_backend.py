"""
Unit Tests for AWS Backend API & Telemetry Schema Validation
"""

import pytest
import json
from backend.schema import validate_telemetry_payload
from backend.app import lambda_handler, handle_telemetry_post, handle_telemetry_get


def test_schema_validation_valid():
    valid_payload = {
        "well_id": "BW-001",
        "timestamp": "2026-10-10T09:00:00Z",
        "data_source": "simulated",
        "depth_to_water_m": 48.2,
        "temperature_c": 28.5,
        "pump_state": "OFF",
        "pump_run_minutes": 42,
        "measurement_valid": True
    }
    is_valid, err = validate_telemetry_payload(valid_payload)
    assert is_valid is True
    assert err == ""


def test_schema_validation_invalid_depth():
    invalid_payload = {
        "well_id": "BW-001",
        "timestamp": "2026-10-10T09:00:00Z",
        "data_source": "simulated",
        "depth_to_water_m": 999.0,  # Out of bounds (> 300m)
        "temperature_c": 28.5,
        "pump_state": "OFF",
        "pump_run_minutes": 42,
        "measurement_valid": True
    }
    is_valid, err = validate_telemetry_payload(invalid_payload)
    assert is_valid is False
    assert "out of physical bounds" in err


def test_schema_validation_missing_field():
    incomplete_payload = {
        "well_id": "BW-001",
        "timestamp": "2026-10-10T09:00:00Z"
    }
    is_valid, err = validate_telemetry_payload(incomplete_payload)
    assert is_valid is False
    assert "Missing required field" in err


def test_lambda_handler_post_and_get():
    # Test POST valid
    post_event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "well_id": "BW-TEST",
            "timestamp": "2026-10-10T10:00:00Z",
            "data_source": "simulated",
            "depth_to_water_m": 45.0,
            "temperature_c": 26.0,
            "pump_state": "ON",
            "pump_run_minutes": 15,
            "measurement_valid": True
        })
    }
    res_post = lambda_handler(post_event, None)
    assert res_post["statusCode"] == 201
    body = json.loads(res_post["body"])
    assert body["status"] == "success"

    # Test GET
    get_event = {
        "httpMethod": "GET",
        "queryStringParameters": {"well_id": "BW-TEST"}
    }
    res_get = lambda_handler(get_event, None)
    assert res_get["statusCode"] == 200
    get_body = json.loads(res_get["body"])
    assert get_body["status"] == "success"
    assert get_body["count"] >= 1
