"""
Unit Tests for Simulator Module
"""

import pytest
import pandas as pd
from simulator.simulator import BorewellSimulator, generate_sample_csv


def test_simulator_scenarios():
    sim = BorewellSimulator(well_id="BW-TEST", baseline_depth_m=40.0)

    # Test Normal Scenario
    df_normal = sim.generate_series(scenario="normal", duration_hours=24, interval_minutes=15)
    assert not df_normal.empty
    assert len(df_normal) == 96  # 24 hours * 4 samples/hr
    assert "depth_to_water_m" in df_normal.columns
    assert "pump_state" in df_normal.columns
    assert (df_normal["depth_to_water_m"] >= 40.0).all()

    # Test Weak Recharge Scenario
    df_weak = sim.generate_series(scenario="weak_recharge", duration_hours=24, interval_minutes=15)
    assert not df_weak.empty

    # Test Over-pumping Scenario
    df_over = sim.generate_series(scenario="over_pumping", duration_hours=24, interval_minutes=15)
    assert not df_over.empty
    # Over-pumping should reach a deeper maximum drawdown than normal
    assert df_over["depth_to_water_m"].max() > df_normal["depth_to_water_m"].max()


def test_generate_sample_csv(tmp_path):
    csv_file = tmp_path / "test_readings.csv"
    df = generate_sample_csv(str(csv_file))
    assert csv_file.exists()
    assert len(df) == 288
