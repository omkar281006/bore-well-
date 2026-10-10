"""
BoreWise API: one router shared by the AWS Lambda handler and the local HTTP server.

Routes
  GET  /health                         service check
  POST /telemetry                      one reading (schema v2, see docs/telemetry-schema.md)
  POST /telemetry/batch                {"records": [...]} up to 500 readings
  GET  /telemetry?well_id=BW-001       latest readings (newest first; the Streamlit dashboard uses this)
  GET  /wells                          registered wells with their latest reading
  POST /wells                          register or update a well (bore type, depth, intake, pump flow, fractures, rainfall)
  GET  /wells/{well_id}?days=45        full analysis: forecast, findings, cycles, daily series, last 72 h

Run locally:  python backend/app.py            (http://localhost:8000, data kept in data/local_store/)
Deploy:       sam build && sam deploy --guided  (see backend/template.yaml)
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, unquote, urlparse

if __package__ in (None, ""):
    # Lambda (flat package) or `python backend/app.py`
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analysis import DEFAULT_WELL, analyze, parse_ts  # type: ignore
    from schema import normalize_record, validate_telemetry_payload, validate_well_config  # type: ignore
    from storage import get_store  # type: ignore
else:
    from .analysis import DEFAULT_WELL, analyze, parse_ts
    from .schema import normalize_record, validate_telemetry_payload, validate_well_config
    from .storage import get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("BoreWiseBackend")

MAX_BATCH = 500
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}

Response = Tuple[int, Dict[str, Any]]


# ---------------------------------------------------------------- handlers
def handle_telemetry_post(payload: Dict[str, Any]) -> Response:
    """Validates and stores one telemetry record."""
    ok, err = validate_telemetry_payload(payload)
    if not ok:
        logger.warning("Validation failed: %s", err)
        return 400, {"status": "error", "message": "Schema validation failed", "error": err, "received_payload": payload}
    rec = normalize_record(payload)
    get_store().put_readings([rec])
    return 201, {"status": "success", "message": "Telemetry record ingested and stored successfully",
                 "well_id": rec["well_id"], "timestamp": rec["timestamp"], "data_source": rec["data_source"]}


def handle_telemetry_batch(body: Dict[str, Any]) -> Response:
    records = body.get("records") if isinstance(body, dict) else None
    if not isinstance(records, list) or not records:
        return 400, {"status": "error", "message": "Body must be {\"records\": [...]} with at least one record"}
    if len(records) > MAX_BATCH:
        return 400, {"status": "error", "message": f"At most {MAX_BATCH} records per batch"}
    good: List[Dict[str, Any]] = []
    rejected = []
    for i, rec in enumerate(records):
        ok, err = validate_telemetry_payload(rec)
        if ok:
            good.append(normalize_record(rec))
        else:
            rejected.append({"index": i, "error": err})
    if good:
        get_store().put_readings(good)
    status = 201 if not rejected else (207 if good else 400)
    return status, {"status": "success" if not rejected else "partial" if good else "error",
                    "accepted": len(good), "rejected": rejected[:20], "rejected_count": len(rejected)}


def handle_telemetry_get(well_id: str = "BW-001", limit: int = 100) -> Response:
    """Most recent readings for a well, newest first."""
    records = get_store().query_readings(well_id, limit=limit, newest_first=True)
    return 200, {"status": "success", "count": len(records), "well_id": well_id, "telemetry": records}


def handle_well_post(cfg: Dict[str, Any]) -> Response:
    ok, err = validate_well_config(cfg)
    if not ok:
        return 400, {"status": "error", "message": "Well config validation failed", "error": err}
    merged = {**DEFAULT_WELL, **(get_store().get_well(cfg["well_id"]) or {}), **cfg}
    get_store().put_well(merged)
    return 201, {"status": "success", "well": {k: v for k, v in merged.items() if k != "rain_mm"}}


def handle_wells_list() -> Response:
    store = get_store()
    out = []
    for w in store.list_wells():
        latest = store.query_readings(w["well_id"], limit=1, newest_first=True)
        out.append({**{k: v for k, v in w.items() if k != "rain_mm"}, "latest": latest[0] if latest else None})
    return 200, {"status": "success", "count": len(out), "wells": out}


def handle_well_get(well_id: str, days: float = 45) -> Response:
    store = get_store()
    newest = store.query_readings(well_id, limit=1, newest_first=True)
    if not newest:
        return 404, {"status": "error", "message": f"No telemetry for well '{well_id}' yet"}
    since_ts = parse_ts(newest[0]["timestamp"]) - dt.timedelta(days=days)
    since = since_ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # stored timestamps are UTC
    readings = store.query_readings(well_id, since=since) or newest
    cfg = store.get_well(well_id) or {**DEFAULT_WELL, "well_id": well_id}
    result = analyze(readings, cfg)
    rain = cfg.get("rain_mm") or {}
    if rain and result.get("season_start"):
        start = dt.datetime.fromisoformat(result["season_start"]).date()
        result["rain_by_day"] = [round(float(rain.get((start + dt.timedelta(days=d)).isoformat(), 0.0)), 2) for d in range(366)]
    result["well"] = {k: v for k, v in result["well"].items() if k != "rain_mm"}
    result["window_days"] = days
    return 200, {"status": "success", **result}


# ---------------------------------------------------------------- router
def route(method: str, path: str, query: Dict[str, str], body: Any) -> Response:
    path = "/" + path.strip("/")
    parts = [unquote(p) for p in path.split("/") if p]
    if method == "OPTIONS":
        return 200, {}
    if parts == ["health"] and method == "GET":
        return 200, {"status": "ok", "store": get_store().kind, "time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if parts == ["telemetry"]:
        if method == "POST":
            return handle_telemetry_post(body)
        if method == "GET":
            return handle_telemetry_get(query.get("well_id", "BW-001"), int(query.get("limit", 100)))
    if parts == ["telemetry", "batch"] and method == "POST":
        return handle_telemetry_batch(body)
    if parts == ["wells"]:
        if method == "GET":
            return handle_wells_list()
        if method == "POST":
            return handle_well_post(body)
    if len(parts) == 2 and parts[0] == "wells" and method == "GET":
        try:
            days = min(370.0, max(1.0, float(query.get("days", 45))))
        except ValueError:
            return 400, {"status": "error", "message": "'days' must be a number"}
        return handle_well_get(parts[1], days)
    if parts == [] and method == "GET":
        return 200, {"status": "ok", "service": "BoreWise API", "routes": ["/health", "/telemetry", "/telemetry/batch", "/wells", "/wells/{well_id}"]}
    return 405 if parts in (["telemetry"], ["wells"]) else 404, {"status": "error", "message": f"No route for {method} {path}"}


def _parse_body(raw: Any) -> Any:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw)


# ---------------------------------------------------------------- AWS Lambda
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Works with API Gateway HTTP API (payload v2), REST API (v1) and Lambda Function URLs."""
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path") or "/"
    query = event.get("queryStringParameters") or {}
    try:
        raw = event.get("body")
        if raw and event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw).decode("utf-8")
        body = _parse_body(raw)
    except Exception as exc:  # noqa: BLE001
        return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"status": "error", "message": f"Invalid JSON body: {exc}"})}
    try:
        status, payload = route(method, path, query, body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error")
        status, payload = 500, {"status": "error", "message": str(exc)}
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(payload, default=str)}


# ---------------------------------------------------------------- local server
class LocalHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        url = urlparse(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = _parse_body(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"status": "error", "message": f"Malformed request: {exc}"})
            return
        try:
            status, payload = route(method, url.path, query, body)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error")
            status, payload = 500, {"status": "error", "message": str(exc)}
        self._send(status, payload)

    def do_OPTIONS(self):  # noqa: N802
        self._send(200, {})

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        self._handle("POST")

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("BOREWISE_VERBOSE"):
            super().log_message(fmt, *args)


def run_local_server(port: int = 8000) -> None:
    os.environ.setdefault("BOREWISE_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "local_store"))
    store = get_store()
    httpd = ThreadingHTTPServer(("", port), LocalHTTPRequestHandler)
    print(f"[BoreWise] API running at http://localhost:{port}  (store: {store.kind}, data: {os.environ.get('BOREWISE_DATA_DIR')})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local server.")
        httpd.server_close()


if __name__ == "__main__":
    run_local_server(int(os.environ.get("PORT", 8000)))
