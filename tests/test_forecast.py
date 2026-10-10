"""Short-horizon forecast (Streamlit dashboard) tests."""

import datetime as dt

import pandas as pd

from simulator.forecast import analyze_drawdown_and_recovery, forecast_water_level_risk
from simulator.simulator import BorewellSimulator

START = dt.datetime(2027, 1, 5, tzinfo=dt.timezone.utc)


def test_analyze_drawdown_and_recovery():
    df = BorewellSimulator().generate_series(scenario="normal", duration_hours=48, interval_minutes=15, start_time=START)
    stats = analyze_drawdown_and_recovery(df)
    assert stats["total_cycles"] > 0
    assert stats["avg_drawdown_m"] > 0
    assert 0 <= stats["avg_recovery_pct"] <= 100


def test_forecast_water_level_risk():
    sim = BorewellSimulator()
    df_normal = sim.generate_series(scenario="normal", duration_hours=48, interval_minutes=15, start_time=START)
    fc = forecast_water_level_risk(df_normal, threshold_depth_m=55.0, forecast_hours=24)
    assert fc["risk_level"] == "Normal"
    assert len(fc["p10_series"]) == len(fc["p50_series"]) == len(fc["p90_series"]) == 24
    assert fc["p10_forecast_depth_m"] <= fc["p50_forecast_depth_m"] <= fc["p90_forecast_depth_m"]

    df_over = sim.generate_series(scenario="over_pumping", duration_hours=96, interval_minutes=15, start_time=START)
    fc_over = forecast_water_level_risk(df_over, threshold_depth_m=48.0, forecast_hours=48)
    assert fc_over["risk_level"] in ("Warning", "High Risk")


def test_forecast_is_stable_hour_to_hour():
    """Regression: the old trend used first and last reading, so the risk flipped with the pump state."""
    df = BorewellSimulator().generate_series(scenario="normal", duration_hours=72, interval_minutes=15, start_time=START)
    levels = {forecast_water_level_risk(df.iloc[: h * 4], threshold_depth_m=55.0)["risk_level"] for h in range(60, 73)}
    assert levels == {"Normal"}


def test_forecast_empty_data():
    fc = forecast_water_level_risk(pd.DataFrame())
    assert fc["risk_level"] == "Unknown"
