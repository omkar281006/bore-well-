"""
BoreWise Physics-Inspired Groundwater Telemetry Simulator

Generates realistic time-series data for a single virtual borewell based on a 
transparent, mass-balance drawdown and exponential recovery model.

Scenarios supported:
1. 'normal': Periodic pumping with healthy aquifer recharge. Water depth fully recovers.
2. 'weak_recharge': Low aquifer transmissivity/recharge rate. Recovery is slow, leaving residual drawdown.
3. 'over_pumping': Intensive/prolonged pumping without adequate recovery windows, driving water depth to critical levels.
"""

import math
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd


class BorewellSimulator:
    """
    Transparent physics-inspired aquifer drawdown & recovery simulator.
    
    Depth parameters:
    - depth_to_water_m: Distance from wellhead rim (0m) to water surface in metres.
    - Higher value = lower water table / deeper drawdown.
    """

    def __init__(
        self,
        well_id: str = "BW-001",
        baseline_depth_m: float = 40.0,
        drawdown_rate_m_per_min: float = 0.05,
        normal_recovery_k: float = 0.08,
        data_source: str = "simulated"
    ):
        self.well_id = well_id
        self.baseline_depth_m = baseline_depth_m
        self.drawdown_rate = drawdown_rate_m_per_min
        self.normal_recovery_k = normal_recovery_k
        self.data_source = data_source

    def generate_series(
        self,
        scenario: str = "normal",
        duration_hours: int = 72,
        interval_minutes: int = 15,
        start_time: Optional[datetime.datetime] = None
    ) -> pd.DataFrame:
        """
        Generates time-series data for a given scenario.
        
        Args:
            scenario: 'normal', 'weak_recharge', or 'over_pumping'
            duration_hours: total duration in hours (e.g., 72 hours = 3 days)
            interval_minutes: sampling resolution (e.g., 15 mins)
            start_time: start datetime (defaults to 3 days ago UTC)
            
        Returns:
            pd.DataFrame with telemetry columns matching shared schema.
        """
        if start_time is None:
            # Fixed reproducible default start time or current time
            start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=duration_hours)

        total_steps = int((duration_hours * 60) / interval_minutes)
        records: List[Dict[str, Any]] = []

        current_depth = self.baseline_depth_m
        pump_consecutive_mins = 0
        
        # Scenario configuration multipliers
        if scenario == "weak_recharge":
            recovery_k = self.normal_recovery_k * 0.25  # 75% slower recovery
            pump_duty_cycle = (120, 240)  # 2 hrs ON, 4 hrs OFF
        elif scenario == "over_pumping":
            recovery_k = self.normal_recovery_k * 0.40  # slow recovery
            pump_duty_cycle = (360, 120)  # 6 hrs ON, 2 hrs OFF (excessive)
        else:  # normal
            recovery_k = self.normal_recovery_k
            pump_duty_cycle = (120, 480)  # 2 hrs ON, 8 hrs OFF (sustainable)

        on_duration, off_duration = pump_duty_cycle

        for i in range(total_steps):
            timestamp = start_time + datetime.timedelta(minutes=i * interval_minutes)
            cycle_minute = (i * interval_minutes) % (on_duration + off_duration)
            
            is_pump_on = cycle_minute < on_duration

            if is_pump_on:
                pump_state = "ON"
                pump_consecutive_mins += interval_minutes
                # Drawdown equation: Depth increases (water level falls)
                # Adds slight non-linear resistance as drawdown deepens
                additional_drawdown = self.drawdown_rate * interval_minutes * (1.0 + (current_depth - self.baseline_depth_m) * 0.02)
                current_depth += additional_drawdown
            else:
                pump_state = "OFF"
                pump_consecutive_mins = 0
                # Recovery equation: Exponential recovery towards baseline_depth_m
                # dS/dt = -k * (current_depth - baseline_depth)
                residual = current_depth - self.baseline_depth_m
                recovery_amount = residual * (1.0 - math.exp(-recovery_k * (interval_minutes / 60.0)))
                current_depth = max(self.baseline_depth_m, current_depth - recovery_amount)

            # Add minor ambient thermal/measurement variation (25°C to 30°C)
            temp = round(25.0 + 3.0 * math.sin(i * 0.1) + (1.5 if is_pump_on else 0.0), 2)
            
            records.append({
                "well_id": self.well_id,
                "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data_source": self.data_source,
                "depth_to_water_m": round(current_depth, 2),
                "temperature_c": temp,
                "pump_state": pump_state,
                "pump_run_minutes": pump_consecutive_mins if is_pump_on else 0,
                "measurement_valid": True,
                "scenario": scenario
            })

        return pd.DataFrame(records)


def generate_sample_csv(filepath: str = "data/sample_readings.csv") -> pd.DataFrame:
    """Generates default 72-hour simulated dataset and writes to CSV."""
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    sim = BorewellSimulator()
    df = sim.generate_series(scenario="normal", duration_hours=72, interval_minutes=15)
    df.to_csv(filepath, index=False)
    return df


if __name__ == "__main__":
    df_sample = generate_sample_csv("data/sample_readings.csv")
    print(f"Sample telemetry generated successfully with {len(df_sample)} records!")
    print(df_sample.head())
