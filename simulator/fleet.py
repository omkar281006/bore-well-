"""
Telemetry fleet: drives virtual borewells and posts their readings to the BoreWise API,
exactly as ESP32 units in the field would.

Examples (from the project root):

  # Backfill 30 days of an over-pumping society well into the local API, then stream live
  python -m simulator.fleet --api http://localhost:8000 --scenario overpump --days 30 --live

  # Same against AWS
  python -m simulator.fleet --api https://abc123.execute-api.ap-south-1.amazonaws.com --scenario fracture

  # Several wells at once (well ids BW-001, BW-002, ...)
  python -m simulator.fleet --api http://localhost:8000 --scenario healthy,clog,interf --days 20

In --live mode the simulated clock runs at --speed hours per real second (default 0.25,
so one pump cycle passes in a few seconds and the web app visibly updates).
On ECS Fargate the same command runs as the always-on simulator fleet.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .physics import BORES, Borewell, build_config
from .telemetry import stream

BATCH = 500


def _request(method: str, url: str, body: Any = None, retries: int = 3) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code < 500 or attempt == retries - 1:
                raise SystemExit(f"{method} {url} failed with {exc.code}: {detail[:400]}")
        except urllib.error.URLError as exc:
            if attempt == retries - 1:
                raise SystemExit(f"Cannot reach {url}: {exc.reason}. Is the API running?")
        time.sleep(1.5 * (attempt + 1))
    return {}


def register_well(api: str, well_id: str, name: str, sc: Dict[str, Any], well: Borewell) -> None:
    rain = {(well.season_start + dt.timedelta(days=d)).date().isoformat(): round(v, 2) for d, v in enumerate(well.rain)}
    cfg = {
        "well_id": well_id, "name": name, "bore_type": sc["bore"], "depth_m": sc["depth"], "intake_m": sc["intake"],
        "pump_flow_m3_day": sc["Q"], "fractures": [{"d": f["d"], "T": f["T"]} for f in sc["fr"]],
        "scenario": sc["id"], "data_source": "simulated", "location": "Pune (simulated)", "rain_mm": rain,
    }
    _request("POST", f"{api}/wells", cfg)


def post_records(api: str, records: List[Dict[str, Any]]) -> int:
    sent = 0
    for i in range(0, len(records), BATCH):
        res = _request("POST", f"{api}/telemetry/batch", {"records": records[i:i + BATCH]})
        sent += int(res.get("accepted", 0))
        if res.get("rejected_count"):
            print(f"  warning: {res['rejected_count']} records rejected, e.g. {res['rejected'][:1]}", file=sys.stderr)
    return sent


def main(argv: List[str] = None) -> None:
    p = argparse.ArgumentParser(description="Post simulated borewell telemetry to the BoreWise API.")
    p.add_argument("--api", default="http://localhost:8000", help="API base URL")
    p.add_argument("--scenario", default="overpump", help="comma-separated: healthy, overpump, fracture, interf, clog, weak, wear, dry, sensor, weak_recharge")
    p.add_argument("--bore", default="open", choices=sorted(BORES))
    p.add_argument("--days", type=float, default=30, help="days of history to backfill, ending where the scenario gets interesting")
    p.add_argument("--well-id", default="BW-001", help="id for the first well; more wells get -002, -003 ...")
    p.add_argument("--name", default="Sahyadri Heights CHS, Baner")
    p.add_argument("--live", action="store_true", help="keep streaming after the backfill")
    p.add_argument("--speed", type=float, default=0.25, help="simulated hours per real second in --live mode")
    args = p.parse_args(argv)

    api = args.api.rstrip("/")
    health = _request("GET", f"{api}/health")
    print(f"API ok ({health.get('store', '?')} store)")

    wells = []
    for n, scenario in enumerate(s.strip() for s in args.scenario.split(",") if s.strip()):
        well_id = args.well_id if n == 0 else f"{args.well_id.rsplit('-', 1)[0]}-{n + 1:03d}"
        sc = build_config(scenario, args.bore)
        well = Borewell(sc)
        probe = Borewell(dict(sc))
        probe.warm_up()
        target = probe.t / 24
        start = max(sc["startDay"], target - args.days)
        while well.t < start * 24:
            well.step()
        register_well(api, well_id, args.name if n == 0 else f"{args.name} ({scenario})", sc, well)
        records = list(stream(well, well_id, max(target - start, 0.5) * 24))
        sent = post_records(api, records)
        print(f"{well_id}: {scenario} on {sc['bore_name']}, sent {sent} readings up to {well.timestamp():%d %b %Y %H:%M}")
        wells.append((well_id, well))

    if not args.live:
        print("Done. Open the web app with VITE_API_URL pointing at this API to see the wells.")
        return

    print(f"Streaming live at {args.speed} simulated h per second. Ctrl+C to stop.")
    tick = 2.0
    try:
        while True:
            t0 = time.time()
            for well_id, well in wells:
                recs = list(stream(well, well_id, args.speed * tick))
                if recs:
                    post_records(api, recs)
            last = wells[0][1]
            print(f"  {last.timestamp():%d %b %H:%M}  depth {last.dl:6.2f} m  pump {'ON ' if last.pump_on else 'OFF'}", end="\r", flush=True)
            time.sleep(max(0.0, tick - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
