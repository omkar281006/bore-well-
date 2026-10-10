"""
Smoke test for a deployed (or local) BoreWise API. Writes documented evidence to docs/deployment-evidence.md.

    python scripts/smoke_test.py --api https://abc123.execute-api.ap-south-1.amazonaws.com
    python scripts/smoke_test.py --api http://localhost:8000          # local rehearsal

Checks the Part 2 completion condition: the API accepts valid telemetry, rejects invalid records, stores readings
and returns analysis. It also registers the demo wells from config/wells.json and backfills their telemetry.
Smoke records go to a separate well id (SMOKE-<time>) so they never mix with the demo wells.
Uses only the standard library (plus the project's simulator for the fleet step).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def call(method: str, url: str, body: Any = None, raw: bytes = None) -> Tuple[int, Any, float]:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            status, text = res.status, res.read().decode()
    except urllib.error.HTTPError as exc:
        status, text = exc.code, exc.read().decode("utf-8", "replace")
    ms = (time.time() - t0) * 1000
    try:
        return status, json.loads(text or "{}"), ms
    except ValueError:
        return status, text, ms


def iso(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--stack", default="borewise")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "wells.json"))
    ap.add_argument("--skip-fleet", action="store_true", help="do not register/backfill the demo wells")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "deployment-evidence.md"))
    args = ap.parse_args(argv)
    api = args.api.rstrip("/")

    now = dt.datetime.now(dt.timezone.utc)
    smoke_id = f"SMOKE-{now:%m%d%H%M}"
    base = {"well_id": smoke_id, "timestamp": iso(now - dt.timedelta(minutes=1)), "data_source": "simulated",
            "depth_to_water_m": 48.2, "temperature_c": 28.5, "pump_state": "OFF", "pump_run_minutes": 0,
            "measurement_valid": True}
    rows: List[Dict[str, Any]] = []
    health_store = "?"

    def check(name: str, expect: str, fn: Callable[[], Tuple[bool, str, float]]) -> bool:
        try:
            ok, got, ms = fn()
        except Exception as exc:  # report, keep going
            ok, got, ms = False, f"{type(exc).__name__}: {exc}", 0.0
        rows.append({"name": name, "expect": expect, "got": got, "ok": ok, "ms": ms})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {got}")
        return ok

    def post(body, raw=None):
        return call("POST", f"{api}/telemetry", body, raw)

    # ---- service
    def t_health():
        nonlocal health_store
        s, b, ms = call("GET", f"{api}/health")
        health_store = b.get("store", "?") if isinstance(b, dict) else "?"
        local = "localhost" in api or "127.0.0.1" in api
        ok = s == 200 and b.get("status") == "ok" and (local or health_store == "dynamodb")
        return ok, f"{s}, store={health_store}", ms
    check("GET /health", "200, status ok; store=dynamodb on AWS", t_health)

    # ---- accepts valid telemetry
    def t_valid():
        s, b, ms = post(base)
        return s == 201, f"{s} {b.get('message', b)}", ms
    check("Valid record", "201", t_valid)

    def t_compat():
        rec = {**base, "timestamp": iso(now), "data_source": "bench_tested", "pump_state": "UNKNOWN", "flow_lpm": 118.5}
        s, b, ms = post(rec)
        return s == 201 and b.get("data_source") == "bench-tested", f"{s}, stored data_source={b.get('data_source')}", ms
    check("Plan schema: bench_tested + pump_state UNKNOWN + flow_lpm", "201, stored as bench-tested", t_compat)

    def t_gated():
        s, b, ms = post({**base, "timestamp": iso(now - dt.timedelta(minutes=2)), "pump_state": "ON", "pump_run_minutes": 5,
                         "depth_to_water_m": None, "measurement_valid": False, "pump_current_a": 6.1})
        return s == 201, f"{s}", ms
    check("Pumping record with gated (null) depth", "201", t_gated)

    # ---- rejects invalid records
    invalid = [
        ("Missing field (depth_to_water_m)", {k: v for k, v in base.items() if k != "depth_to_water_m"}, None),
        ("Depth out of range (999 m)", {**base, "depth_to_water_m": 999}, None),
        ("Timestamp without timezone", {**base, "timestamp": "2026-10-11T09:00:00"}, None),
        ("Bad pump_state", {**base, "pump_state": "MAYBE"}, None),
        ("Unknown data_source", {**base, "data_source": "guessed"}, None),
        ("Device timestamp 3 h in the future", {**base, "data_source": "field-measured", "timestamp": iso(now + dt.timedelta(hours=3))}, None),
        ("Malformed JSON", None, b"{not json"),
    ]
    for name, body, raw in invalid:
        def t_bad(body=body, raw=raw):
            s, b, ms = post(body, raw)
            msg = b.get("error") or b.get("message") if isinstance(b, dict) else str(b)[:80]
            return s == 400, f"{s} {msg}", ms
        check(f"Reject: {name}", "400 with reason", t_bad)

    # ---- stale flag
    def t_stale():
        s, b, ms = post({**base, "data_source": "field_measured", "timestamp": iso(now - dt.timedelta(days=3))})
        return s == 201 and b.get("stale") is True, f"{s}, stale={b.get('stale')}", ms
    check("Reading 3 days late is stored but flagged stale", "201, stale=true", t_stale)

    # ---- batch
    def t_batch():
        recs = [{**base, "timestamp": iso(now - dt.timedelta(minutes=10 + i))} for i in range(5)] + [{**base, "depth_to_water_m": -4}]
        s, b, ms = call("POST", f"{api}/telemetry/batch", {"records": recs})
        return s == 207 and b.get("accepted") == 5 and b.get("rejected_count") == 1, \
            f"{s}, accepted={b.get('accepted')}, rejected={b.get('rejected_count')}", ms
    check("Batch of 6 with 1 bad record", "207, 5 accepted, 1 rejected", t_batch)

    # ---- stores readings
    def t_stored():
        s, b, ms = call("GET", f"{api}/telemetry?well_id={smoke_id}&limit=50")
        recs = b.get("telemetry", []) if isinstance(b, dict) else []
        stale = sum(1 for r in recs if r.get("stale"))
        return s == 200 and len(recs) >= 9 and stale == 1, f"{s}, {len(recs)} stored, {stale} stale", ms
    check(f"Readings stored and read back ({smoke_id})", "200, 9 stored, 1 stale", t_stored)

    # ---- demo wells from config + analysis
    profiles: List[Dict[str, Any]] = []
    if not args.skip_fleet:
        from simulator import fleet
        profiles = fleet.load_profiles(args.config)

        def t_fleet():
            t0 = time.time()
            fleet.main(["--api", api, "--config", args.config])
            s, b, _ = call("GET", f"{api}/wells")
            ids = {w["well_id"] for w in b.get("wells", [])}
            want = {p["well_id"] for p in profiles}
            return want <= ids, f"registered {sorted(want & ids)}", (time.time() - t0) * 1000
        check("Register + backfill wells from config/wells.json", f"{len(profiles)} wells listed", t_fleet)

        for p in profiles:
            def t_well(p=p):
                s, b, ms = call("GET", f"{api}/wells/{p['well_id']}?days=30")
                if s != 200 or not isinstance(b, dict):
                    return False, f"{s}", ms
                fc = b.get("forecast", {})
                titles = ", ".join(f.get("title", "?") for f in b.get("findings", [])[:3]) or "none"
                want_thr = round(p["intake_m"] - p["min_submergence_m"], 2)
                ok = bool(b.get("readings")) and fc.get("state") is not None and b.get("threshold_m") == want_thr
                return ok, (f"200, forecast={fc.get('state')}, water table {b.get('water_table_m')} m, "
                            f"threshold {b.get('threshold_m')} m, findings: {titles}"), ms
            check(f"GET /wells/{p['well_id']} returns analysis ({p['scenario']}, {p['bore_type']})",
                  "200 with forecast, threshold, findings", t_well)

    passed = sum(r["ok"] for r in rows)
    write_evidence(args, api, health_store, now, rows, smoke_id)
    print(f"\n{passed}/{len(rows)} checks passed. Evidence written to {os.path.relpath(args.out, ROOT)}")
    return 0 if passed == len(rows) else 1


def write_evidence(args, api, store, when, rows, smoke_id) -> None:
    passed = sum(r["ok"] for r in rows)
    lines = [
        "# BoreWise deployment evidence",
        "",
        "Generated by `scripts/smoke_test.py`. Re-run it after every deploy; this file is overwritten.",
        "",
        "| | |", "|---|---|",
        f"| Run at | {when.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))):%d %b %Y %H:%M} IST |",
        f"| API | `{api}` |",
        f"| Stack / region | `{args.stack}` / `{args.region}` |",
        f"| Storage reported by `/health` | `{store}` |",
        f"| Smoke well id | `{smoke_id}` (kept apart from demo wells) |",
        f"| Client | Python {platform.python_version()} on {platform.system()} |",
        f"| **Result** | **{passed} of {len(rows)} checks passed** |",
        "",
        "## Checks",
        "",
        "| # | Check | Expected | Got | Latency | Result |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        got = str(r["got"]).replace("|", "\\|").replace("\n", " ")[:220]
        lines.append(f"| {i} | {r['name']} | {r['expect']} | {got} | {r['ms']:.0f} ms | {'✅' if r['ok'] else '❌'} |")
    lines += [
        "",
        "## Completion condition (Part 2)",
        "",
        "> A deployed API accepts valid telemetry, rejects invalid records, stores readings and returns analysis.",
        "",
        "- accepts valid telemetry: checks 2 to 4",
        "- rejects invalid records: the `Reject:` checks",
        "- stores readings: the stale-flag, batch and read-back checks",
        "- returns analysis: the `GET /wells/...` checks",
        "",
        "## Also capture for the submission",
        "",
        "- Screenshot: CloudFormation stack `" + args.stack + "` in CREATE_COMPLETE / UPDATE_COMPLETE",
        "- Screenshot: DynamoDB table `" + args.stack + "-telemetry` → Explore items, filtered on `BW-001`",
        "- Screenshot: the web app in **Live API** mode showing BW-001",
        "- Screenshot: Billing → Budgets showing `borewise-hackathon`",
        "",
        "All telemetry here is `simulated` except the smoke records labelled bench/field, which only test validation.",
    ]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
