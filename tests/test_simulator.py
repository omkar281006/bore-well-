"""Simulator tests: original API, physical bounds, and agreement with the web app's engine."""

import datetime as dt

from simulator.physics import BORES, Borewell, build_config, generate_rain
from simulator.simulator import BorewellSimulator, generate_sample_csv
from simulator.telemetry import scenario_readings

START = dt.datetime(2027, 1, 5, tzinfo=dt.timezone.utc)


def test_simulator_scenarios():
    sim = BorewellSimulator(well_id="BW-TEST", baseline_depth_m=40.0)
    df_normal = sim.generate_series(scenario="normal", duration_hours=24, interval_minutes=15, start_time=START)
    assert len(df_normal) == 96  # 24 h * 4 samples/h
    assert {"depth_to_water_m", "pump_state", "measurement_valid", "pump_current_a"} <= set(df_normal.columns)
    # Never shallower than the starting water table (allowing 10 cm of sounding noise).
    assert (df_normal["depth_to_water_m"] >= 39.9).all()

    df_weak = sim.generate_series(scenario="weak_recharge", duration_hours=24, interval_minutes=15, start_time=START)
    df_over = sim.generate_series(scenario="over_pumping", duration_hours=24, interval_minutes=15, start_time=START)
    assert df_weak["depth_to_water_m"].max() > df_normal["depth_to_water_m"].max()  # tight aquifer draws down further
    assert df_over["pump_state"].eq("ON").sum() > df_normal["pump_state"].eq("ON").sum()  # more pumping hours


def test_depths_stay_physical():
    """Regression: the old model reached 860 m in over-pumping. Water can't go below the intake."""
    for scenario in ("normal", "weak_recharge", "over_pumping"):
        df = BorewellSimulator().generate_series(scenario=scenario, duration_hours=168, interval_minutes=15, start_time=START)
        assert df["depth_to_water_m"].max() <= BORES["open"]["intake"] + 0.5, scenario


def test_generate_sample_csv(tmp_path):
    csv_file = tmp_path / "test_readings.csv"
    df = generate_sample_csv(str(csv_file))
    assert csv_file.exists()
    assert len(df) == 288


def test_matches_web_app_engine():
    """Values computed with frontend/src/sim (node) for the same scenarios; the Python port must agree."""
    expected = {"healthy": (22.6718, 22.8183), "overpump": (54.1390, 54.8645), "dry": (85.1466, 86.2135)}
    for sid, (swl, dl) in expected.items():
        w = Borewell(build_config(sid, "open"))
        w.warm_up()
        assert abs(w.swl - swl) < 1e-3 and abs(w.dl - dl) < 1e-3, sid
    rain = generate_rain(11)
    assert abs(rain[246] - 11.86989037914677) < 1e-9


def test_telemetry_protocol():
    recs = scenario_readings("healthy", days=2)
    assert recs, "no telemetry generated"
    ts = [r["timestamp"] for r in recs]
    assert len(ts) == len(set(ts)), "timestamps must be unique per well"
    on = [r for r in recs if r["pump_state"] == "ON"]
    assert on and all(r["depth_to_water_m"] is None and r["measurement_valid"] is False for r in on), "sounding is gated while pumping"
    assert any(r.get("event") == "pump_off" for r in recs)
