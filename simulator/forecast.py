"""
BoreWise Recovery Analytics & Risk Forecasting Engine

Provides diagnostic calculations for borewell drawdown, recovery rate,
and quantile-based stochastic risk forecasting (P10, P50, P90).
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple


def analyze_drawdown_and_recovery(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyzes historical pumping cycles to compute drawdown depth, 
    recovery rates, and recovery percentage ratios.
    
    Returns diagnostic summary dict.
    """
    if df.empty or "depth_to_water_m" not in df or "pump_state" not in df:
        return {
            "total_cycles": 0,
            "avg_drawdown_m": 0.0,
            "max_drawdown_m": 0.0,
            "avg_recovery_rate_m_per_hr": 0.0,
            "avg_recovery_pct": 100.0,
            "residual_drawdown_m": 0.0,
            "cycle_details": []
        }

    df_clean = df.copy()
    df_clean["timestamp"] = pd.to_datetime(df_clean["timestamp"])
    df_clean = df_clean.sort_values("timestamp").reset_index(drop=True)

    cycles = []
    current_cycle = None
    
    for i in range(len(df_clean)):
        row = df_clean.iloc[i]
        p_state = row["pump_state"]
        depth = row["depth_to_water_m"]
        ts = row["timestamp"]

        if p_state == "ON":
            if current_cycle is None:
                current_cycle = {
                    "start_time": ts,
                    "start_depth": depth,
                    "max_depth": depth,
                    "end_pump_time": ts,
                    "post_pump_depths": [],
                    "post_pump_times": []
                }
            else:
                current_cycle["max_depth"] = max(current_cycle["max_depth"], depth)
                current_cycle["end_pump_time"] = ts
        else:
            if current_cycle is not None:
                current_cycle["post_pump_depths"].append(depth)
                current_cycle["post_pump_times"].append(ts)

        # Detect transition or end of off period
        if i < len(df_clean) - 1:
            next_p_state = df_clean.iloc[i + 1]["pump_state"]
            if current_cycle is not None and next_p_state == "ON" and p_state == "OFF":
                # Close current cycle
                cycles.append(current_cycle)
                current_cycle = None

    if current_cycle is not None:
        cycles.append(current_cycle)

    cycle_summaries = []
    drawdowns = []
    recoveries_pct = []
    recovery_rates = []

    for idx, c in enumerate(cycles):
        drawdown_m = max(0.0, c["max_depth"] - c["start_depth"])
        drawdowns.append(drawdown_m)

        if c["post_pump_depths"]:
            final_recovered_depth = c["post_pump_depths"][-1]
            recov_m = max(0.0, c["max_depth"] - final_recovered_depth)
            
            # Recovery percentage
            recov_pct = (recov_m / drawdown_m * 100.0) if drawdown_m > 0 else 100.0
            recov_pct = min(100.0, recov_pct)
            recoveries_pct.append(recov_pct)

            # Recovery rate m/hr
            total_off_secs = (c["post_pump_times"][-1] - c["end_pump_time"]).total_seconds()
            off_hrs = total_off_secs / 3600.0
            recov_rate = (recov_m / off_hrs) if off_hrs > 0 else 0.0
            recovery_rates.append(recov_rate)

            cycle_summaries.append({
                "cycle_id": idx + 1,
                "start_time": c["start_time"].isoformat(),
                "drawdown_m": round(drawdown_m, 2),
                "recovery_pct": round(recov_pct, 1),
                "recovery_rate_m_per_hr": round(recov_rate, 2),
                "residual_depth_m": round(final_recovered_depth, 2)
            })

    first_depth = df_clean["depth_to_water_m"].iloc[0]
    latest_depth = df_clean["depth_to_water_m"].iloc[-1]
    residual_drawdown = max(0.0, latest_depth - first_depth)

    return {
        "total_cycles": len(cycles),
        "avg_drawdown_m": round(float(np.mean(drawdowns)), 2) if drawdowns else 0.0,
        "max_drawdown_m": round(float(np.max(drawdowns)), 2) if drawdowns else 0.0,
        "avg_recovery_rate_m_per_hr": round(float(np.mean(recovery_rates)), 2) if recovery_rates else 0.0,
        "avg_recovery_pct": round(float(np.mean(recoveries_pct)), 1) if recoveries_pct else 100.0,
        "residual_drawdown_m": round(float(residual_drawdown), 2),
        "cycle_details": cycle_summaries
    }


def forecast_water_level_risk(
    df: pd.DataFrame,
    threshold_depth_m: float = 55.0,
    forecast_hours: int = 48,
    num_simulations: int = 100
) -> Dict[str, Any]:
    """
    Computes threshold-crossing risk forecast and P10/P50/P90 depth quantiles.
    
    Quantile definitions:
    - P10: Optimistic forecast quantile (10th percentile of depth = shallowest water level)
    - P50: Median baseline forecast depth projection
    - P90: Pessimistic forecast quantile (90th percentile of depth = deepest drawdown level / highest risk)
    """
    if df.empty or len(df) < 5:
        return {
            "status": "Insufficient Data",
            "risk_level": "Unknown",
            "threshold_m": threshold_depth_m,
            "current_depth_m": 0.0,
            "horizon_hours": None,
            "p10_forecast_depth_m": 0.0,
            "p50_forecast_depth_m": 0.0,
            "p90_forecast_depth_m": 0.0,
            "forecast_times": [],
            "p10_series": [],
            "p50_series": [],
            "p90_series": [],
            "recommendation": "Collect more telemetry to compute reliable risk forecasts.",
            "explanation": "At least 5 valid readings are required for stochastic trajectory estimation."
        }

    df_clean = df.copy()
    df_clean["timestamp"] = pd.to_datetime(df_clean["timestamp"])
    df_clean = df_clean.sort_values("timestamp").reset_index(drop=True)

    latest_row = df_clean.iloc[-1]
    current_depth = float(latest_row["depth_to_water_m"])
    last_time = latest_row["timestamp"]

    # Calculate recent trend (net change rate in m/hour over last 24 hours or total window)
    time_diff_hrs = (last_time - df_clean["timestamp"].iloc[0]).total_seconds() / 3600.0
    if time_diff_hrs > 0:
        net_depth_change = current_depth - float(df_clean["depth_to_water_m"].iloc[0])
        drift_rate_m_per_hr = net_depth_change / time_diff_hrs
    else:
        drift_rate_m_per_hr = 0.0

    # Calculate volatility (standard deviation of step-by-step depth changes)
    depth_diffs = df_clean["depth_to_water_m"].diff().dropna()
    volatility = float(np.std(depth_diffs)) if len(depth_diffs) > 1 else 0.1

    # Run Monte Carlo forecast simulation for forecast_hours
    hourly_steps = list(range(1, forecast_hours + 1))
    forecast_timestamps = [(last_time + pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in hourly_steps]

    simulated_trajectories = np.zeros((num_simulations, forecast_hours))
    
    # Use fixed random seed for deterministic consistency across re-renders
    rng = np.random.default_rng(42)

    for sim_idx in range(num_simulations):
        sim_depth = current_depth
        for h_idx in range(forecast_hours):
            # Drift component + stochastic noise component
            noise = rng.normal(0, max(0.05, volatility * 0.5))
            sim_depth += (drift_rate_m_per_hr + noise)
            sim_depth = max(10.0, sim_depth)  # Physical lower limit depth
            simulated_trajectories[sim_idx, h_idx] = sim_depth

    # Calculate percentiles across simulations for each hourly step
    p10_series = np.percentile(simulated_trajectories, 10, axis=0).round(2).tolist()
    p50_series = np.percentile(simulated_trajectories, 50, axis=0).round(2).tolist()
    p90_series = np.percentile(simulated_trajectories, 90, axis=0).round(2).tolist()

    final_p10 = p10_series[-1]
    final_p50 = p50_series[-1]
    final_p90 = p90_series[-1]

    # Calculate estimated horizon until threshold breach (using P50 median path)
    horizon_hours = None
    for h_idx, depth in enumerate(p50_series):
        if depth >= threshold_depth_m:
            horizon_hours = h_idx + 1
            break

    # Determine Risk Status Level
    if current_depth >= threshold_depth_m or (horizon_hours is not None and horizon_hours <= 12):
        risk_level = "High Risk"
        status_color = "red"
    elif (horizon_hours is not None and horizon_hours <= 36) or final_p90 >= threshold_depth_m:
        risk_level = "Warning"
        status_color = "yellow"
    else:
        risk_level = "Normal"
        status_color = "green"

    # Generate plain-language explanations & actionable recommendations
    if risk_level == "High Risk":
        explanation = (
            f"Water level depth ({current_depth:.1f}m) is critically close to or exceeding "
            f"the operating threshold ({threshold_depth_m:.1f}m). "
            f"Net drawdown rate is {drift_rate_m_per_hr:+.2f} m/hr with high risk of dry pump run."
        )
        recommendation = (
            "IMMEDIATE ACTION REQUIRED: Cease continuous pumping for 12-24 hours to allow aquifer recharge. "
            "Reduce daily pump duty cycle by at least 50% and inspect pump intake depth."
        )
    elif risk_level == "Warning":
        explanation = (
            f"Water level depth is currently {current_depth:.1f}m. Based on recent usage patterns, "
            f"the P90 forecast predicts depth may reach {final_p90:.1f}m within {forecast_hours} hours, "
            f"approaching the {threshold_depth_m:.1f}m threshold."
        )
        recommendation = (
            "ADVISORY: Increase post-pumping rest intervals by 2-4 hours. "
            "Avoid multi-hour continuous pumping runs during peak drawdown periods."
        )
    else:
        explanation = (
            f"Borewell operating within safe limits ({current_depth:.1f}m depth vs {threshold_depth_m:.1f}m threshold). "
            f"Recharge rate is balancing pumping extraction with stable trend ({drift_rate_m_per_hr:+.2f} m/hr)."
        )
        recommendation = (
            "SUSTAINABLE OPERATION: Maintain current pumping schedule. "
            "Continue periodic monitoring to detect any seasonal water table drops."
        )

    return {
        "risk_level": risk_level,
        "status_color": status_color,
        "threshold_m": threshold_depth_m,
        "current_depth_m": round(current_depth, 2),
        "drift_rate_m_per_hr": round(drift_rate_m_per_hr, 3),
        "horizon_hours": horizon_hours,
        "p10_forecast_depth_m": final_p10,
        "p50_forecast_depth_m": final_p50,
        "p90_forecast_depth_m": final_p90,
        "forecast_times": forecast_timestamps,
        "p10_series": p10_series,
        "p50_series": p50_series,
        "p90_series": p90_series,
        "explanation": explanation,
        "recommendation": recommendation
    }
