"""
BoreWise recovery analytics and short-horizon risk forecast (teammate API, fixed).

Two functions used by the Streamlit dashboard:

* analyze_drawdown_and_recovery(df): per-cycle drawdown, recovery % and recovery rate.
* forecast_water_level_risk(df, threshold, hours): P10/P50/P90 depth bands and a
  Normal / Warning / High Risk level.

Fix: the old forecast took its trend from the first and last reading, so the answer
depended on whether the pump happened to be running at that moment (the same data gave
Normal, Warning and High Risk one hour apart). The trend now comes from the settled
pre-pump water table, read just before each pump start, so pumping no longer moves it.
For the season-long dry-up date use backend.analysis.analyze(), which the API and the
web app use.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, format="mixed")
    out = out.sort_values("timestamp").reset_index(drop=True)
    if "measurement_valid" not in out:
        out["measurement_valid"] = True
    return out


def _cycles(df: pd.DataFrame) -> List[Dict[str, Any]]:
    cycles: List[Dict[str, Any]] = []
    cur = None
    prev_on = False
    last_off_depth = None
    for row in df.itertuples(index=False):
        on = row.pump_state == "ON"
        depth = float(row.depth_to_water_m) if pd.notna(row.depth_to_water_m) else None
        if on and not prev_on:
            if cur is not None:
                cycles.append(cur)
            cur = {"start_time": row.timestamp, "start_depth": last_off_depth if last_off_depth is not None else depth,
                   "max_depth": depth if depth is not None else -np.inf, "end_pump_time": row.timestamp, "post": []}
        if on and cur is not None:
            if depth is not None:
                cur["max_depth"] = max(cur["max_depth"], depth)
            cur["end_pump_time"] = row.timestamp
        if not on and depth is not None:
            if cur is not None and prev_on:
                cur["max_depth"] = max(cur["max_depth"], depth)  # first reading after switch-off is the deepest we can measure
            if cur is not None:
                cur["post"].append((row.timestamp, depth))
            last_off_depth = depth
        prev_on = on
    if cur is not None:
        cycles.append(cur)
    return [c for c in cycles if c["start_depth"] is not None and np.isfinite(c["max_depth"])]


def analyze_drawdown_and_recovery(df: pd.DataFrame) -> Dict[str, Any]:
    empty = {"total_cycles": 0, "avg_drawdown_m": 0.0, "max_drawdown_m": 0.0, "avg_recovery_rate_m_per_hr": 0.0,
             "avg_recovery_pct": 100.0, "residual_drawdown_m": 0.0, "cycle_details": []}
    if df.empty or "depth_to_water_m" not in df or "pump_state" not in df:
        return empty
    d = _clean(df)
    cycles = _cycles(d)
    drawdowns, recov_pcts, recov_rates, details = [], [], [], []
    for idx, c in enumerate(cycles):
        drawdown = max(0.0, c["max_depth"] - c["start_depth"])
        drawdowns.append(drawdown)
        if not c["post"]:
            continue
        end_t, end_d = c["post"][-1]
        recovered = max(0.0, c["max_depth"] - end_d)
        pct = min(100.0, recovered / drawdown * 100) if drawdown > 0 else 100.0
        hours = (end_t - c["end_pump_time"]).total_seconds() / 3600
        rate = recovered / hours if hours > 0 else 0.0
        recov_pcts.append(pct)
        recov_rates.append(rate)
        details.append({"cycle_id": idx + 1, "start_time": c["start_time"].isoformat(), "drawdown_m": round(drawdown, 2),
                        "recovery_pct": round(pct, 1), "recovery_rate_m_per_hr": round(rate, 2), "residual_depth_m": round(end_d, 2)})
    pre = [c["start_depth"] for c in cycles]
    residual = max(0.0, pre[-1] - pre[0]) if len(pre) >= 2 else 0.0
    return {
        "total_cycles": len(cycles),
        "avg_drawdown_m": round(float(np.mean(drawdowns)), 2) if drawdowns else 0.0,
        "max_drawdown_m": round(float(np.max(drawdowns)), 2) if drawdowns else 0.0,
        "avg_recovery_rate_m_per_hr": round(float(np.mean(recov_rates)), 2) if recov_rates else 0.0,
        "avg_recovery_pct": round(float(np.mean(recov_pcts)), 1) if recov_pcts else 100.0,
        "residual_drawdown_m": round(float(residual), 2),
        "cycle_details": details,
    }


def forecast_water_level_risk(df: pd.DataFrame, threshold_depth_m: float = 55.0, forecast_hours: int = 48,
                              num_simulations: int = 100) -> Dict[str, Any]:
    """
    P10 = optimistic (shallowest), P50 = median, P90 = pessimistic (deepest) depth.
    The P90 band includes the typical drawdown of one pump run on top of the water-table trend,
    because that is the level the pump intake actually sees.
    """
    if df.empty or len(df) < 5:
        return {"status": "Insufficient Data", "risk_level": "Unknown", "status_color": "gray", "threshold_m": threshold_depth_m,
                "current_depth_m": 0.0, "drift_rate_m_per_hr": 0.0, "horizon_hours": None, "p10_forecast_depth_m": 0.0,
                "p50_forecast_depth_m": 0.0, "p90_forecast_depth_m": 0.0, "forecast_times": [], "p10_series": [], "p50_series": [],
                "p90_series": [], "recommendation": "Collect more telemetry to compute reliable risk forecasts.",
                "explanation": "At least 5 valid readings are required."}
    d = _clean(df)
    valid = d[(d["measurement_valid"]) & d["depth_to_water_m"].notna()]
    last_time = d["timestamp"].iloc[-1]
    current_depth = float(valid["depth_to_water_m"].iloc[-1]) if len(valid) else float(d["depth_to_water_m"].iloc[-1])

    cycles = _cycles(d)
    pre = [(c["start_time"], c["start_depth"]) for c in cycles]
    if len(pre) >= 2:
        hrs = np.array([(t - pre[0][0]).total_seconds() / 3600 for t, _ in pre])
        lv = np.array([v for _, v in pre])
        slope, intercept = np.polyfit(hrs, lv, 1)
        resid = lv - (slope * hrs + intercept)
        drift = float(slope)
        base_now = float(slope * ((last_time - pre[0][0]).total_seconds() / 3600) + intercept)
        sigma = float(np.std(resid)) if len(resid) > 2 else 0.05
    else:
        drift, base_now, sigma = 0.0, current_depth, 0.05
    typical_dd = float(np.median([c["max_depth"] - c["start_depth"] for c in cycles])) if cycles else 0.0

    rng = np.random.default_rng(42)
    steps = np.arange(1, forecast_hours + 1)
    # Uncertainty in the trend grows with horizon; level noise stays at the observed scatter.
    slopes = drift + rng.normal(0, max(abs(drift) * 0.3, 0.002), size=(num_simulations, 1))
    paths = base_now + slopes * steps + rng.normal(0, max(sigma, 0.03), size=(num_simulations, forecast_hours))
    p10 = np.percentile(paths, 10, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p90 = np.percentile(paths, 90, axis=0) + typical_dd

    horizon = next((int(h) for h, v in zip(steps, p50 + typical_dd) if v >= threshold_depth_m), None)
    final_p90 = float(p90[-1])
    peak_now = base_now + typical_dd
    if peak_now >= threshold_depth_m or (horizon is not None and horizon <= 12):
        risk, color = "High Risk", "red"
    elif (horizon is not None and horizon <= 36) or final_p90 >= threshold_depth_m:
        risk, color = "Warning", "yellow"
    else:
        risk, color = "Normal", "green"

    if risk == "High Risk":
        explanation = (f"Pumping draws the water down to about {peak_now:.1f} m, at or past the {threshold_depth_m:.1f} m limit. "
                       f"The water table itself is moving {drift:+.3f} m/hr.")
        recommendation = "Act now: shorten each pump run and leave longer rest between runs so the well can refill."
    elif risk == "Warning":
        explanation = (f"The water table is at {base_now:.1f} m and moving {drift:+.3f} m/hr. With a typical {typical_dd:.1f} m drawdown per run, "
                       f"the pessimistic P90 band reaches {final_p90:.1f} m within {forecast_hours} h.")
        recommendation = "Advisory: add 2–4 hours of rest between runs and avoid long continuous runs."
    else:
        explanation = (f"Pumping peaks near {peak_now:.1f} m against a {threshold_depth_m:.1f} m limit, "
                       f"and the water table is moving {drift:+.3f} m/hr.")
        recommendation = "Sustainable: keep the current schedule and keep monitoring for the seasonal decline."

    times = [(last_time + pd.Timedelta(hours=int(h))).strftime("%Y-%m-%dT%H:%M:%SZ") for h in steps]
    return {
        "risk_level": risk, "status_color": color, "threshold_m": threshold_depth_m, "current_depth_m": round(current_depth, 2),
        "water_table_m": round(base_now, 2), "typical_drawdown_m": round(typical_dd, 2), "drift_rate_m_per_hr": round(drift, 4),
        "horizon_hours": horizon, "p10_forecast_depth_m": round(float(p10[-1]), 2), "p50_forecast_depth_m": round(float(p50[-1]), 2),
        "p90_forecast_depth_m": round(final_p90, 2), "forecast_times": times, "p10_series": np.round(p10, 2).tolist(),
        "p50_series": np.round(p50, 2).tolist(), "p90_series": np.round(p90, 2).tolist(), "explanation": explanation,
        "recommendation": recommendation,
    }
