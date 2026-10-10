"""
BoreWise borewell telemetry simulator (teammate API, rebuilt on the shared physics).

Keeps the original `BorewellSimulator.generate_series()` interface used by the Streamlit
dashboard and tests, but the numbers now come from `simulator.physics`, the same model
the 3D web app runs. The old model let drawdown feed on itself and reached 860 m in an
over-pumping run; depths are now bounded by the bore and the pump intake.

Scenarios: 'normal', 'weak_recharge', 'over_pumping' (original names) plus every
scenario in physics.SCENARIOS ('healthy', 'overpump', 'fracture', 'interf', 'clog',
'weak', 'wear', 'dry', 'sensor').
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Any, Dict, List, Optional

import pandas as pd

if __package__ in (None, ""):  # allow `python simulator/simulator.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from simulator.physics import STEP_HOURS, Borewell, build_config, season_start_for  # noqa: E402
else:
    from .physics import STEP_HOURS, Borewell, build_config, season_start_for


class BorewellSimulator:
    """
    Generates evenly spaced telemetry for one virtual borewell.

    Depth is metres from the wellhead (0 m) down to the water surface; larger means deeper water.
    While the pump runs the acoustic sounding is gated, so those rows carry the simulator's true
    level with measurement_valid = False (a real device would send no depth then).
    """

    def __init__(
        self,
        well_id: str = "BW-001",
        baseline_depth_m: float = 40.0,
        drawdown_rate_m_per_min: Optional[float] = None,  # kept for compatibility; physics now sets drawdown
        normal_recovery_k: Optional[float] = None,  # kept for compatibility; transmissivity now sets refill
        data_source: str = "simulated",
        bore: str = "open",
        seed: int = 4242,
    ):
        self.well_id = well_id
        self.baseline_depth_m = baseline_depth_m
        self.data_source = data_source
        self.bore = bore
        self.seed = seed

    def generate_series(
        self,
        scenario: str = "normal",
        duration_hours: int = 72,
        interval_minutes: int = 15,
        start_time: Optional[dt.datetime] = None,
    ) -> pd.DataFrame:
        if start_time is None:
            start_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=duration_hours)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=dt.timezone.utc)
        season = season_start_for(start_time)
        start_day = (start_time - season).total_seconds() / 86400

        sc = build_config(scenario, self.bore, swl0=self.baseline_depth_m, startDay=start_day)
        well = Borewell(sc, season_start=season, seed=self.seed)

        total = int(duration_hours * 60 / interval_minutes)
        steps_per_sample = max(1, round(interval_minutes / 60 / STEP_HOURS))
        records: List[Dict[str, Any]] = []
        on_since = None
        for i in range(total):
            for _ in range(steps_per_sample if i else 0):
                well.step()
            if well.pump_on and on_since is None:
                on_since = well.t
            if not well.pump_on:
                on_since = None
            valid = not well.pump_on
            depth = well.measured_depth() if valid else well.dl
            records.append({
                "well_id": self.well_id,
                "timestamp": (start_time + dt.timedelta(minutes=i * interval_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data_source": self.data_source,
                "depth_to_water_m": round(depth, 2),
                "temperature_c": round(well.temp, 2),
                "pump_state": "ON" if well.pump_on else "OFF",
                "pump_run_minutes": round((well.t - on_since) * 60) if on_since is not None else 0,
                "pump_current_a": round(well.current_a, 2),
                "measurement_valid": valid,
                "scenario": scenario,
            })
        return pd.DataFrame(records)


def generate_sample_csv(filepath: str = "data/sample_readings.csv") -> pd.DataFrame:
    """Writes the default 72-hour simulated dataset (15-minute readings) to CSV."""
    folder = os.path.dirname(filepath)
    if folder:
        os.makedirs(folder, exist_ok=True)
    start = dt.datetime(2027, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
    df = BorewellSimulator().generate_series(scenario="normal", duration_hours=72, interval_minutes=15, start_time=start)
    df.to_csv(filepath, index=False)
    return df


if __name__ == "__main__":
    df_sample = generate_sample_csv("data/sample_readings.csv")
    print(f"Sample telemetry generated with {len(df_sample)} records.")
    print(df_sample.head())
