"""
Unit Tests for Analytics & Risk Forecast Engine
"""

import pytest
import pandas as pd
from simulator.simulator import BorewellSimulator
from simulator.forecast import analyze_drawdown_and_recovery, forecast_water_level_risk


def test_analyze_drawdown_and_recovery():
    sim = BorewellSimulator()
    df = sim.generate_series(scenario="normal", duration_hours=48, interval_minutes=15)
    
    stats = analyze_drawdown_and_recovery(df)
    assert isinstance(stats, dict)
    assert "total_cycles" in stats
    assert "avg_drawdown_m" in stats
    assert "avg_recovery_pct" in stats
    assert stats["total_cycles"] > 0


def test_forecast_water_level_risk():
    sim = BorewellSimulator()
    df_normal = sim.generate_series(scenario="normal", duration_hours=48, interval_minutes=15)
    
    # Test Normal Risk Forecast
    fc_normal = forecast_water_level_risk(df_normal, threshold_depth_m=55.0, forecast_hours=24)
    assert fc_normal["risk_level"] in ("Normal", "Warning", "High Risk")
    assert len(fc_normal["p10_series"]) == 24
    assert len(fc_normal["p50_series"]) == 24
    assert len(fc_normal["p90_series"]) == 24
    assert fc_normal["p10_forecast_depth_m"] <= fc_normal["p90_forecast_depth_m"]

    # Test High Risk Over-pumping Scenario
    df_over = sim.generate_series(scenario="over_pumping", duration_hours=96, interval_minutes=15)
    fc_over = forecast_water_level_risk(df_over, threshold_depth_m=48.0, forecast_hours=48)
    assert fc_over["risk_level"] in ("Warning", "High Risk")


def test_forecast_empty_data():
    df_empty = pd.DataFrame()
    fc = forecast_water_level_risk(df_empty)
    assert fc["risk_level"] == "Unknown"
