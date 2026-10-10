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


# ---------------------------------------------------------------- Part 2: schema compatibility and stale data
import datetime as _dt

from backend.schema import threshold_depth


def _iso(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_pump_state_unknown_and_flow_lpm_accepted():
    assert validate_telemetry_payload({**VALID, "pump_state": "UNKNOWN"}) == (True, "")
    assert validate_telemetry_payload({**VALID, "flow_lpm": 118.5}) == (True, "")
    assert validate_telemetry_payload({**VALID, "flow_lpm": None}) == (True, "")
    assert not validate_telemetry_payload({**VALID, "flow_lpm": -1})[0]
    assert not validate_telemetry_payload({**VALID, "flow_lpm": "fast"})[0]
    assert not validate_telemetry_payload({**VALID, "pump_state": "MAYBE"})[0]
    assert normalize_record(VALID)["flow_lpm"] is None


def test_underscore_provenance_normalised_to_hyphen():
    now = _dt.datetime.now(_dt.timezone.utc)
    for raw, stored in (("bench_tested", "bench-tested"), ("field_measured", "field-measured"), ("bench-tested", "bench-tested")):
        rec = {**VALID, "data_source": raw, "timestamp": _iso(now)}
        assert validate_telemetry_payload(rec) == (True, "")
        assert normalize_record(rec)["data_source"] == stored
    assert not validate_telemetry_payload({**VALID, "data_source": "made_up"})[0]


def test_future_timestamp_rejected_for_device_data_only():
    future = _iso(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2))
    ok, err = validate_telemetry_payload({**VALID, "data_source": "field-measured", "timestamp": future})
    assert not ok and "future" in err
    assert validate_telemetry_payload({**VALID, "data_source": "simulated", "timestamp": future})[0]  # model clock


def test_late_device_reading_is_flagged_stale():
    now = _dt.datetime(2026, 10, 11, 6, 0, tzinfo=_dt.timezone.utc)
    late = {**VALID, "data_source": "field-measured", "timestamp": "2026-10-09T05:00:00Z"}   # 49 h old
    fresh = {**VALID, "data_source": "field-measured", "timestamp": "2026-10-11T04:00:00Z"}  # 2 h old (buffered)
    assert normalize_record(late, received_at=now)["stale"] is True
    assert normalize_record(fresh, received_at=now)["stale"] is False
    assert normalize_record(VALID, received_at=now + _dt.timedelta(days=400))["stale"] is False  # simulated backfill
    assert normalize_record(fresh, received_at=now)["received_at"] == "2026-10-11T06:00:00Z"


def test_ingest_stores_stale_flag():
    old = _iso(_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=3))
    status, body = handle_telemetry_post({**VALID, "data_source": "bench_tested", "timestamp": old})
    assert status == 201 and body["stale"] is True and body["data_source"] == "bench-tested"
    status, body = handle_telemetry_get("BW-001")
    assert body["telemetry"][0]["stale"] is True


def test_min_submergence_sets_threshold():
    assert threshold_depth({"intake_m": 103}) == 101.0
    assert threshold_depth({"intake_m": 103, "min_submergence_m": 4.5}) == 98.5
    assert validate_well_config({"well_id": "BW-9", "depth_m": 120, "intake_m": 103, "min_submergence_m": 3})[0]
    assert not validate_well_config({"well_id": "BW-9", "depth_m": 120, "intake_m": 103, "min_submergence_m": -1})[0]


# ---------------------------------------------------------------- DynamoDB paging (fake table, no AWS needed)
def test_dynamo_store_pages_through_scan_and_query():
    import sys
    import types

    from backend.storage import META_SK, DynamoStore

    class Cond:  # tiny stand-in for boto3.dynamodb.conditions
        def __init__(self, fn): self.fn = fn
        def __and__(self, other): return Cond(lambda i: self.fn(i) and other.fn(i))

    class Field:
        def __init__(self, name): self.name = name
        def eq(self, v): return Cond(lambda i: i.get(self.name) == v)
        def gt(self, v): return Cond(lambda i: i.get(self.name) > v)
        def gte(self, v): return Cond(lambda i: i.get(self.name) >= v)

    class FakeTable:
        PAGE = 7  # a real table returns at most 1 MB per call

        def __init__(self): self.items = {}
        def put_item(self, Item): self.items[(Item["well_id"], Item["timestamp"])] = Item
        def get_item(self, Key): return {"Item": self.items.get((Key["well_id"], Key["timestamp"]))} if (Key["well_id"], Key["timestamp"]) in self.items else {}

        def _page(self, rows, kwargs):
            start = kwargs.get("ExclusiveStartKey", 0)
            page = rows[start:start + min(self.PAGE, kwargs.get("Limit", self.PAGE))]
            res = {"Items": page}
            if start + len(page) < len(rows):
                res["LastEvaluatedKey"] = start + len(page)
            return res

        def scan(self, **kw):  # filter is applied after the page is read, like DynamoDB
            rows = sorted(self.items.values(), key=lambda i: (i["well_id"], i["timestamp"]))
            res = self._page(rows, kw)
            res["Items"] = [i for i in res["Items"] if kw["FilterExpression"].fn(i)]
            return res

        def query(self, **kw):
            rows = sorted((i for i in self.items.values() if kw["KeyConditionExpression"].fn(i)),
                          key=lambda i: i["timestamp"], reverse=not kw["ScanIndexForward"])
            return self._page(rows, kw)

    stub = types.ModuleType("boto3.dynamodb.conditions")
    stub.Key = stub.Attr = Field
    saved = {k: sys.modules.get(k) for k in ("boto3", "boto3.dynamodb", "boto3.dynamodb.conditions")}
    sys.modules.update({"boto3": types.ModuleType("boto3"), "boto3.dynamodb": types.ModuleType("boto3.dynamodb"),
                        "boto3.dynamodb.conditions": stub})
    try:
        table = FakeTable()
        store = DynamoStore(table)
        for w in ("BW-001", "BW-002", "BW-003"):
            store.put_well({"well_id": w, "intake_m": 100})
            for k in range(20):
                table.put_item({"well_id": w, "timestamp": f"2027-01-01T00:{k:02d}:00Z", "depth_to_water_m": 40})
        assert [w["well_id"] for w in store.list_wells()] == ["BW-001", "BW-002", "BW-003"]
        got = store.query_readings("BW-002")
        assert len(got) == 20 and all(r["timestamp"] != META_SK for r in got)
        assert len(store.query_readings("BW-002", limit=10, newest_first=True)) == 10
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
