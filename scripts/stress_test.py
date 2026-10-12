"""
Stress test for a BoreWise API (local or AWS): load, bad data and fault detection, with a written report.

    python scripts/stress_test.py --api http://localhost:8000
    python scripts/stress_test.py --api https://abc123.execute-api.ap-south-1.amazonaws.com --workers 6

Phases
  1. Ingest   register N wells (9 failure scenarios x 4 bore types = 36 by default) and upload their telemetry
              in parallel batches of 500, retrying HTTP 429 (API Gateway throttling) with backoff
  2. Read     W parallel workers hit GET /wells/{id}, /fleet and /telemetry for D seconds
  3. Abuse    a barrage of invalid records (every one must be rejected with 400) and mixed batches (207)
  4. Detect   every well's analysis is checked for the finding its scenario should produce

Wells use ids ST-<scenario>-<bore> so they never mix with the demo wells BW-001..003.
On AWS, the default run writes about 400,000 readings (~0.50 USD on DynamoDB on-demand); use --bores open,screen to halve it.
Standard library only (plus the project's simulator).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from simulator.physics import BORES, Borewell, build_config  # noqa: E402
from simulator.telemetry import stream  # noqa: E402

# The finding each scenario should raise (None = no warning expected).
EXPECTED: Dict[str, Optional[str]] = {
    "healthy": None,
    "overpump": "Dry before the monsoon",
    "fracture": "Fracture dewatered",
    "interf": "Level drops while your pump is off",
    "clog": "Well clogging",
    "weak": "Weak monsoon",
    "wear": "Pump delivering less water",
    "dry": "Pump cut off",
    "sensor": "Depth reading not responding",
}
WARNING_SEVS = {"crit", "act", "fault"}
# Stronger outcomes that also count: an over-pumped well that has already run dry has been caught.
ALSO_OK: Dict[str, Tuple[str, ...]] = {"overpump": ("Pump cut off",)}


class Recorder:
    """Thread-safe latency and status log per endpoint."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rows: Dict[str, List[Tuple[int, float]]] = {}
        self.retries_429 = 0

    def add(self, name: str, status: int, ms: float) -> None:
        with self.lock:
            self.rows.setdefault(name, []).append((status, ms))

    def summary(self) -> List[Dict[str, Any]]:
        out = []
        for name, rows in self.rows.items():
            lat = sorted(ms for _, ms in rows)
            codes: Dict[int, int] = {}
            for s, _ in rows:
                codes[s] = codes.get(s, 0) + 1
            pct = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]  # noqa: E731
            out.append({"endpoint": name, "n": len(rows), "p50": pct(0.5), "p95": pct(0.95), "max": lat[-1],
                        "mean": statistics.fmean(lat), "codes": codes})
        return out


def call(rec: Recorder, name: str, method: str, url: str, body: Any = None, raw: bytes = None,
         retry_429: bool = False) -> Tuple[int, Any]:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                status, text = res.status, res.read().decode()
        except urllib.error.HTTPError as exc:
            status, text = exc.code, exc.read().decode("utf-8", "replace")
        except Exception as exc:  # network error
            status, text = 0, str(exc)
        rec.add(name, status, (time.perf_counter() - t0) * 1000)
        if status == 429 and retry_429 and attempt < 5:
            with rec.lock:
                rec.retries_429 += 1
            time.sleep(0.5 * 2 ** attempt + random.random() * 0.3)
            continue
        try:
            return status, json.loads(text or "{}")
        except ValueError:
            return status, text
    return status, text


# ---------------------------------------------------------------- phase 1: ingest
def build_well(scenario: str, bore: str, days: float, extra_days: float) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    sc = build_config(scenario, bore)
    probe = Borewell(dict(sc))
    probe.warm_up()
    target = probe.t / 24
    well = Borewell(sc)
    start = max(sc["startDay"], target - days)
    while well.t < start * 24:
        well.step()
    wid = f"ST-{scenario}-{bore}"
    records = list(stream(well, wid, (target - start + extra_days) * 24))
    rain = {(well.season_start + dt.timedelta(days=d)).date().isoformat(): round(v, 2) for d, v in enumerate(well.rain)}
    cfg = {"well_id": wid, "name": f"Stress {SCEN_NAME.get(scenario, scenario)} ({bore})", "bore_type": bore,
           "depth_m": sc["depth"], "intake_m": sc["intake"], "min_submergence_m": 2.0, "pump_flow_m3_day": sc["Q"],
           "fractures": [{"d": f["d"], "T": f["T"]} for f in sc["fr"]], "scenario": scenario,
           "location": "Stress test (simulated)", "data_source": "simulated", "rain_mm": rain}
    return cfg, records


SCEN_NAME = {"healthy": "healthy", "overpump": "over-pumping", "fracture": "fracture", "interf": "interference", "clog": "clogging",
             "weak": "weak monsoon", "wear": "pump wear", "dry": "dry running", "sensor": "sensor fault"}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--scenarios", default=",".join(EXPECTED))
    ap.add_argument("--bores", default="open,screen,dug,hand")
    ap.add_argument("--days", type=float, default=30, help="days of history before each scenario's key moment")
    ap.add_argument("--extra-days", type=float, default=30, help="days streamed after it")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--duration", type=float, default=45, help="seconds of read load")
    ap.add_argument("--abuse", type=int, default=200, help="invalid records to send")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "stress-test-report.md"))
    args = ap.parse_args(argv)
    api = args.api.rstrip("/")
    rec = Recorder()
    started = dt.datetime.now(dt.timezone.utc)
    status, health = call(rec, "GET /health", "GET", f"{api}/health")
    if status != 200:
        print(f"API not reachable: {status} {health}")
        return 2
    store = health.get("store", "?")
    print(f"API ok, store={store}")

    # ---- 1. ingest
    combos = [(s, b) for b in args.bores.split(",") for s in args.scenarios.split(",")]
    t0 = time.perf_counter()
    wells: List[Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]] = []
    for s, b in combos:
        cfg, records = build_well(s, b, args.days, args.extra_days)
        wells.append((s, b, cfg, records))
    gen_s = time.perf_counter() - t0
    total_records = sum(len(r) for *_, r in wells)
    print(f"Generated {len(wells)} wells, {total_records} readings in {gen_s:.1f}s")

    for s, b, cfg, _ in wells:
        call(rec, "POST /wells", "POST", f"{api}/wells", cfg, retry_429=True)
    batches = [(cfg["well_id"], recs[i:i + 500]) for _, _, cfg, recs in wells for i in range(0, len(recs), 500)]
    accepted = rejected = 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(call, rec, "POST /telemetry/batch (500)", "POST", f"{api}/telemetry/batch", {"records": b}, None, True)
                for _, b in batches]
        for f in as_completed(futs):
            st, body = f.result()
            if isinstance(body, dict):
                accepted += int(body.get("accepted", 0))
                rejected += int(body.get("rejected_count", 0))
    ingest_s = time.perf_counter() - t0
    print(f"Ingested {accepted}/{total_records} readings in {ingest_s:.1f}s ({accepted / max(ingest_s, 1e-9):.0f}/s), rejected {rejected}")

    # ---- 2. read load
    ids = [cfg["well_id"] for _, _, cfg, _ in wells]
    stop_at = time.perf_counter() + args.duration
    reads = {"n": 0}

    def reader(seed: int) -> None:
        r = random.Random(seed)
        while time.perf_counter() < stop_at:
            x = r.random()
            if x < 0.7:
                call(rec, "GET /wells/{id}", "GET", f"{api}/wells/{r.choice(ids)}?days=30", retry_429=True)
            elif x < 0.9:
                call(rec, "GET /telemetry", "GET", f"{api}/telemetry?well_id={r.choice(ids)}&limit=100", retry_429=True)
            else:
                call(rec, "GET /fleet", "GET", f"{api}/fleet?days=30", retry_429=True)
            with rec.lock:
                reads["n"] += 1

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(reader, range(args.workers)))
    read_s = time.perf_counter() - t0
    print(f"Read load: {reads['n']} requests in {read_s:.0f}s ({reads['n'] / read_s:.1f}/s) with {args.workers} workers")

    # ---- 3. abuse
    now = dt.datetime.now(dt.timezone.utc)
    good = {"well_id": "ST-abuse", "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "data_source": "simulated",
            "depth_to_water_m": 40.0, "temperature_c": 27.0, "pump_state": "OFF", "pump_run_minutes": 0, "measurement_valid": True}
    bad_makers = [
        lambda r: (lambda drop: {k: v for k, v in good.items() if k != drop})(r.choice(list(good))),  # a missing field
        lambda r: {**good, "depth_to_water_m": r.choice([-5, 301, 1e9, "deep", True])},                 # impossible depth
        lambda r: {**good, "temperature_c": r.choice([-50, 120, None, "hot"])},                         # impossible temperature
        lambda r: {**good, "pump_state": r.choice(["MAYBE", "on", "", 1])},                              # bad enum
        lambda r: {**good, "timestamp": r.choice(["2026-10-11T09:00:00", "yesterday", "", 12345])},      # bad / naive time
        lambda r: {**good, "data_source": r.choice(["guess", "field", None])},                           # bad provenance
        lambda r: {**good, "data_source": "field-measured", "timestamp": (now + dt.timedelta(hours=r.randint(1, 48))).strftime("%Y-%m-%dT%H:%M:%SZ")},  # future clock
        lambda r: {**good, "well_id": r.choice(["", "x" * 80, "BW#1"])},                                 # bad id
        lambda r: {**good, "measurement_valid": True, "depth_to_water_m": None},                         # null depth claimed valid
    ]
    r = random.Random(7)
    bad = [bad_makers[i % len(bad_makers)](r) for i in range(args.abuse)]
    wrongly_accepted: List[Any] = []

    def send_bad(rec_: Dict[str, Any]) -> None:
        st, body = call(rec, "POST /telemetry (invalid)", "POST", f"{api}/telemetry", rec_, retry_429=True)
        if st != 400:
            wrongly_accepted.append((st, rec_))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(send_bad, bad))
    malformed = [b"{not json", b"", b"[]", b"null", b'{"records": "x"}']
    malformed_ok = 0
    for raw in malformed:
        st, _ = call(rec, "POST /telemetry (malformed)", "POST", f"{api}/telemetry", raw=raw, retry_429=True)
        malformed_ok += st == 400
    st, body = call(rec, "POST /telemetry/batch (mixed)", "POST", f"{api}/telemetry/batch", {"records": [good] * 5 + bad[:5]}, retry_429=True)
    mixed_ok = st == 207 and body.get("accepted") == 5 and body.get("rejected_count") == 5
    print(f"Abuse: {args.abuse - len(wrongly_accepted)}/{args.abuse} invalid records rejected; malformed {malformed_ok}/{len(malformed)}; mixed batch {'ok' if mixed_ok else 'FAILED'}")

    # ---- 4. detection
    det_rows = []
    for s, b, cfg, _ in wells:
        st, body = call(rec, "GET /wells/{id} (detect)", "GET", f"{api}/wells/{cfg['well_id']}?days=30", retry_429=True)
        found = [(f["sev"], f["title"]) for f in body.get("findings", [])] if isinstance(body, dict) else []
        want = EXPECTED.get(s)
        if want:
            ok_titles = (want,) + ALSO_OK.get(s, ())
            hit = any(t.startswith(ok_titles) for _, t in found)
        else:
            hit = not any(sev in WARNING_SEVS for sev, _ in found)
        det_rows.append({"scenario": s, "bore": b, "want": want or "no warning", "hit": hit,
                         "got": "; ".join(t for _, t in found) or "—", "forecast": (body.get("forecast") or {}).get("state") if isinstance(body, dict) else "?"})
    hits = sum(d["hit"] for d in det_rows)
    print(f"Detection: {hits}/{len(det_rows)} wells show the expected finding")

    st, fleet = call(rec, "GET /fleet (final)", "GET", f"{api}/fleet?days=30", retry_429=True)
    write_report(args, api, store, started, rec, len(wells), total_records, accepted, rejected, gen_s, ingest_s,
                 reads["n"], read_s, wrongly_accepted, malformed_ok, len(malformed), mixed_ok, det_rows, fleet if isinstance(fleet, dict) else {})
    print(f"Report written to {os.path.relpath(args.out, ROOT)}")
    server_errors = sum(n for row in rec.summary() for c, n in row["codes"].items() if c >= 500 or c == 0)
    return 0 if (not wrongly_accepted and server_errors == 0 and accepted == total_records) else 1


def write_report(args, api, store, started, rec, n_wells, total, accepted, rejected, gen_s, ingest_s, n_reads, read_s,
                 wrongly, malformed_ok, n_malformed, mixed_ok, det, fleet) -> None:
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    summ = rec.summary()
    server_errors = sum(n for row in summ for c, n in row["codes"].items() if c >= 500 or c == 0)
    hits = sum(d["hit"] for d in det)
    L = [
        "# BoreWise stress test report",
        "",
        "Generated by `scripts/stress_test.py`. Re-run it to refresh; this file is overwritten.",
        "",
        "| | |", "|---|---|",
        f"| Run at | {started.astimezone(ist):%d %b %Y %H:%M} IST |",
        f"| API | `{api}` |",
        f"| Storage (`/health`) | `{store}` |",
        f"| Client | Python {platform.python_version()} on {platform.system()}, {args.workers} parallel workers |",
        f"| Wells | {n_wells} (scenarios × bore types), ids `ST-<scenario>-<bore>` |",
        f"| Readings uploaded | {accepted:,} of {total:,} accepted, {rejected} rejected |",
        f"| Server errors (5xx or no response) | **{server_errors}** |",
        f"| Invalid records wrongly accepted | **{len(wrongly)}** of {args.abuse} |",
        f"| Fault detection | **{hits} / {len(det)}** wells show the expected finding |",
        f"| API Gateway throttling retries (HTTP 429) | {rec.retries_429} |",
        "",
        "## Throughput",
        "",
        "| Phase | Result |",
        "|---|---|",
        f"| Generate telemetry (client side) | {total:,} readings in {gen_s:.1f} s |",
        f"| Ingest, batches of 500 | {accepted:,} readings in {ingest_s:.1f} s = **{accepted / max(ingest_s, 1e-9):,.0f} readings/s** |",
        f"| Read load ({args.duration:.0f} s) | {n_reads:,} requests = **{n_reads / max(read_s, 1e-9):.1f} requests/s** |",
        f"| Malformed bodies rejected | {malformed_ok} / {n_malformed} |",
        f"| Mixed batch (5 good + 5 bad) | {'207, 5 accepted, 5 rejected' if mixed_ok else 'FAILED'} |",
        "",
        "## Latency per endpoint",
        "",
        "| Endpoint | Requests | p50 | p95 | Max | Status codes |",
        "|---|---|---|---|---|---|",
    ]
    for row in sorted(summ, key=lambda r: r["endpoint"]):
        codes = ", ".join(f"{c}×{n}" for c, n in sorted(row["codes"].items()))
        L.append(f"| `{row['endpoint']}` | {row['n']} | {row['p50']:.0f} ms | {row['p95']:.0f} ms | {row['max']:.0f} ms | {codes} |")
    L += ["", "## Fault detection", "",
          f"Each well gets {args.days:g} days of history before its fault starts and {args.extra_days:g} days after, then its analysis is checked. \"Healthy\" passes when no warning (critical, action or sensor fault) is raised; an over-pumped well that has already run dry (\"Pump cut off\") counts as caught.",
          "", "| Scenario | Bore | Expected | Detected? | Findings returned | Forecast |", "|---|---|---|---|---|---|"]
    for d in det:
        L.append(f"| {d['scenario']} | {d['bore']} | {d['want']} | {'✅' if d['hit'] else '❌'} | {d['got']} | {d['forecast']} |")
    by_bore: Dict[str, List[bool]] = {}
    for d in det:
        by_bore.setdefault(d["bore"], []).append(d["hit"])
    L += ["", "| Bore type | Detected |", "|---|---|"] + [f"| {b} | {sum(v)} / {len(v)} |" for b, v in by_bore.items()]
    if fleet:
        L += ["", "## Fleet view after the run", "",
              f"`GET /fleet` returned {fleet.get('count')} wells, {fleet.get('at_risk')} at risk; by status: "
              + ", ".join(f"{k} {v}" for k, v in (fleet.get("by_status") or {}).items() if v) + "."]
    if wrongly:
        L += ["", "## Invalid records that were accepted", ""] + [f"- `{json.dumps(r)[:160]}` → {s}" for s, r in wrongly[:20]]
    L += ["", "## Notes", "",
          "- All telemetry is simulated. Detection numbers measure the analysis on simulated data, not field accuracy.",
          "- Misses on the hand-pump bore are expected: one hand stroke barely moves the water, so clogging, wear, fracture and sensor faults are not visible there.",
          "- On AWS, API Gateway is throttled to 20 requests/s (burst 50); HTTP 429 responses are retried with backoff and counted above."]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
