"""End-to-end tests: simulated telemetry -> API -> analysis, as the web app sees it."""

import datetime as dt
import json

from backend.analysis import analyze, parse_ts as parse
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


# ---------------------------------------------------------------- Part 2: data quality feeds the forecast correctly
def _overpump_rows():
    return scenario_readings("overpump", days=25)


def test_stale_readings_excluded_from_forecast():
    rows = _overpump_rows()
    base = analyze(rows, WELL)
    last = parse(rows[-1]["timestamp"])
    # Late-arriving readings claiming the water came back up to 20 m: flagged stale, so ignored.
    junk = [{**rows[-1], "timestamp": (last + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "depth_to_water_m": 20.0, "pump_state": "OFF", "measurement_valid": True, "stale": True} for h in range(1, 30)]
    r = analyze(rows + junk, WELL)
    assert r["excluded_readings"]["stale"] == len(junk)
    assert r["forecast"]["state"] == base["forecast"]["state"] == "fail"
    assert abs(r["forecast"]["p50"] - base["forecast"]["p50"]) < 1e-9
    # Without the flag the same junk would have moved the forecast.
    unflagged = analyze(rows + [{**j, "stale": False} for j in junk], WELL)
    assert unflagged["forecast"].get("p50") != base["forecast"]["p50"]


def test_unknown_pump_state_is_not_a_transition():
    rows = _overpump_rows()
    base = analyze(rows, WELL)
    last = parse(rows[-1]["timestamp"])
    unk = [{**rows[-1], "timestamp": (last + dt.timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pump_state": "UNKNOWN", "depth_to_water_m": 30.0, "measurement_valid": True} for k in range(1, 9)]
    r = analyze(rows + unk, WELL)
    assert r["excluded_readings"]["unknown_pump_state"] == len(unk)
    assert len(r["cycles"]) == len(base["cycles"])
    assert abs(r["forecast"]["p50"] - base["forecast"]["p50"]) < 1e-9


def test_threshold_follows_min_submergence():
    rows = _overpump_rows()
    two = analyze(rows, {**WELL, "min_submergence_m": 2})
    six = analyze(rows, {**WELL, "min_submergence_m": 6})
    assert two["threshold_m"] == 101.0 and six["threshold_m"] == 97.0
    assert six["forecast"]["limit"] == 97.0
    # Needing more water above the intake brings the dry date forward.
    assert six["forecast"]["p50"] < two["forecast"]["p50"]


def test_fleet_registers_wells_from_config():
    import simulator.fleet as fleet

    reset_store(MemoryStore())
    profiles = fleet.load_profiles("config/wells.json")
    assert 2 <= len(profiles) <= 3

    def fake_request(method, url, body=None, retries=3):
        path = url.split("http://test", 1)[1]
        event = {"httpMethod": method, "path": path, "body": json.dumps(body) if body is not None else None}
        res = lambda_handler(event, None)
        assert res["statusCode"] in (200, 201), res["body"][:300]
        return json.loads(res["body"])

    orig = fleet._request
    fleet._request = fake_request
    try:
        fleet.main(["--api", "http://test", "--config", "config/wells.json"])
    finally:
        fleet._request = orig

    listed = json.loads(lambda_handler({"httpMethod": "GET", "path": "/wells"}, None)["body"])
    ids = {w["well_id"] for w in listed["wells"]}
    assert ids == {p["well_id"] for p in profiles}
    for p in profiles:
        body = json.loads(lambda_handler({"httpMethod": "GET", "path": f"/wells/{p['well_id']}"}, None)["body"])
        assert body["readings"], p["well_id"]
        assert body["threshold_m"] == round(p["intake_m"] - p["min_submergence_m"], 2)
        assert body["well"]["bore_type"] == p["bore_type"]
