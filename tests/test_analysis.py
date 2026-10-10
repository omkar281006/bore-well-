"""End-to-end tests: simulated telemetry -> API -> analysis, as the web app sees it."""

import datetime as dt
import json

from backend.analysis import analyze
from backend.app import lambda_handler
from backend.storage import MemoryStore, reset_store
from simulator.physics import Borewell, build_config
from simulator.telemetry import scenario_readings, stream

WELL = {"well_id": "BW-001", "depth_m": 120, "intake_m": 103, "pump_flow_m3_day": 172.8}


def _run(scenario, extra_days=0):
    sc = build_config(scenario, "open")
    probe = Borewell(dict(sc))
    probe.warm_up()
    well = Borewell(sc)
    start = max(sc["startDay"], probe.t / 24 - 30)
    while well.t < start * 24:
        well.step()
    rows = list(stream(well, "BW-001", (probe.t / 24 - start) * 24 + extra_days * 24))
    rain = {(well.season_start + dt.timedelta(days=d)).date().isoformat(): v for d, v in enumerate(well.rain)}
    return analyze(rows, {**WELL, "fractures": sc["fr"], "rain_mm": rain})


def titles(result):
    return [f["title"] for f in result["findings"]]


def test_overpumping_forecasts_dry_up():
    r = _run("overpump")
    assert r["forecast"]["state"] == "fail"
    assert r["forecast"]["p50"] < 252  # before the monsoon
    assert any(t.startswith("Dry before the monsoon") for t in titles(r))


def test_recovery_fit_estimates_transmissivity():
    r = _run("healthy")
    T = [c["T"] for c in r["cycles"] if c["T"]]
    assert T and all(10 < t < 60 for t in T), T  # simulator truth is about 29 m²/day


def test_clogging_is_told_apart_from_depletion():
    r = _run("clog", extra_days=20)
    assert any(t.startswith("Well clogging") for t in titles(r))


def test_dry_running_cutoff():
    r = _run("dry", extra_days=1)
    assert r["findings"][0]["sev"] == "crit"


def test_sensor_fault_pauses_forecast():
    r = _run("sensor", extra_days=10)
    assert r["forecast"]["state"] == "paused"


def test_api_well_endpoint_round_trip():
    reset_store(MemoryStore())
    recs = scenario_readings("overpump", days=25)
    for i in range(0, len(recs), 500):
        res = lambda_handler({"httpMethod": "POST", "path": "/telemetry/batch", "body": json.dumps({"records": recs[i:i + 500]})}, None)
        assert res["statusCode"] == 201
    lambda_handler({"httpMethod": "POST", "path": "/wells", "body": json.dumps(WELL)}, None)
    res = lambda_handler({"httpMethod": "GET", "path": "/wells/BW-001", "queryStringParameters": {"days": "30"}}, None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert body["forecast"]["state"] == "fail"
    assert body["cycles"][-1]["pts"], "last cycle must carry refill points for the recovery chart"
    assert body["readings"] and body["daily"]
