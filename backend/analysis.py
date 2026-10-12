"""
BoreWise analysis engine: turns raw telemetry into the same diagnosis the 3D app shows.

Input is only what a real device sends (see docs/telemetry-schema.md), never simulator
internals, so the same code works for simulated, bench and field data.

Pipeline
1. Split the stream into pump cycles (pump ON -> pump OFF -> refill readings).
2. Per cycle: drawdown at switch-off, Theis recovery fit -> transmissivity T,
   specific capacity, mean motor current.
3. Per day: pre-pump water table and deepest level.
4. Dry-up forecast: 21-day trend of the pre-pump level against the pump intake,
   P10/P50/P90 dates and the pumping cut that reaches the monsoon.
5. Findings: dry running, sensor fault, fracture dewatering, clogging, pump wear,
   neighbour interference, seasonal decline. Each finding has a message key and
   values so alerts can be written in English, Marathi or Hindi.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MONSOON_ONSET_DAY = 252  # ~10 June counted from 1 October
SEVERITY_RANK = {"ok": 0, "watch": 1, "act": 2, "fault": 2.5, "crit": 3}
SEVERITY_LABEL = {"ok": "Healthy", "watch": "Watch", "act": "Act now", "crit": "Emergency", "fault": "Sensor fault"}
RAIN_MEAN_MM = [1, 0, 2, 10, 25, 140, 190, 130, 120, 75, 25, 5]  # Pune monthly normals, used for the weak-monsoon check
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DEFAULT_WELL = {
    "well_id": "BW-001",
    "name": "Unregistered borewell",
    "bore_type": "open",
    "depth_m": 120.0,
    "intake_m": 103.0,
    "pump_flow_m3_day": 172.8,  # 120 L/min
    "min_submergence_m": 2.0,  # water the pump needs above its intake
    "fractures": [],
}


# ---------------------------------------------------------------- helpers
def parse_ts(value: str) -> dt.datetime:
    ts = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts


def season_start_for(when: dt.datetime) -> dt.datetime:
    local = when.astimezone(IST)
    year = local.year if local.month >= 10 else local.year - 1
    return dt.datetime(year, 10, 1, tzinfo=IST)


def median(values: List[float]) -> float:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    return statistics.median(vals) if vals else math.nan


def ratio(a: float, b: float) -> float:
    return a / b if math.isfinite(a) and math.isfinite(b) and b != 0 else math.nan


def regress(pts: List[Tuple[float, float]]) -> Optional[Dict[str, float]]:
    n = len(pts)
    if n < 3:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx == 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    m = sxy / sxx
    b = my - m * mx
    ss = sum((p[1] - (m * p[0] + b)) ** 2 for p in pts)
    se = math.sqrt(ss / max(1, n - 2) / sxx)
    return {"m": m, "b": b, "se": se}


def fmt_day(season_start: dt.datetime, day: float) -> str:
    d = season_start + dt.timedelta(days=day)
    return f"{d.day} {MONTHS[d.month - 1]}"


def fmt_hm(ts: dt.datetime) -> str:
    return ts.astimezone(IST).strftime("%H:%M")


def r2(x: Optional[float], nd: int = 2) -> Optional[float]:
    return round(x, nd) if x is not None and math.isfinite(x) else None


# ---------------------------------------------------------------- cycles
def split_cycles(rows: List[Dict[str, Any]], flow_m3_day: float) -> List[Dict[str, Any]]:
    """Group rows (sorted, with parsed `_h` hours) into pump cycles and fit each refill."""
    cycles: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    last_valid: Optional[float] = None
    prev_on = False
    for r in rows:
        on = r["pump_state"] == "ON"
        if on and not prev_on:
            if cur is not None:
                cycles.append(cur)
            cur = {"t_on": r["_h"], "t_off": None, "pre": last_valid, "currents": [], "pts": [], "dry": False}
        if on and cur is not None and r.get("pump_current_a") is not None:
            cur["currents"].append(float(r["pump_current_a"]))
        if not on and prev_on and cur is not None:
            cur["t_off"] = r["_h"]
            cur["dry"] = r.get("event") == "dry_cutoff"
        if not on and r.get("measurement_valid") and r.get("depth_to_water_m") is not None:
            d = float(r["depth_to_water_m"])
            if cur is not None and cur["t_off"] is not None:
                cur["pts"].append((r["_h"], d))
            last_valid = d
        prev_on = on
    if cur is not None:
        cycles.append(cur)

    out = []
    for c in cycles:
        if c["t_off"] is None or c["pre"] is None or len(c["pts"]) < 4:
            continue
        first_t, first_d = c["pts"][0]
        if first_t - c["t_off"] > 10 / 60:
            continue  # no reading right after switch-off: cannot measure the drawdown
        s_end = first_d - c["pre"]
        xs, ys = [], []
        for t, d in c["pts"]:
            if t - c["t_off"] < 0.75:
                continue  # skip the first 45 min, dominated by well storage and well loss
            xs.append(math.log10((t - c["t_on"]) / (t - c["t_off"])))
            ys.append(d - c["pre"])
        fit = regress(list(zip(xs, ys))) if len(xs) >= 3 else None
        slope = fit["m"] if fit else math.nan
        T = 2.303 * flow_m3_day / (4 * math.pi * slope) if fit and slope > 0.02 else math.nan
        out.append({
            "t_on": c["t_on"], "t_off": c["t_off"], "day": math.floor(c["t_on"] / 24), "pre": c["pre"], "s_end": s_end,
            "T": T, "slope": slope, "intercept": fit["b"] if fit else math.nan,
            "SC": flow_m3_day / max(s_end, 0.05), "I": statistics.fmean(c["currents"]) if c["currents"] else 0.0,
            "run": c["t_off"] - c["t_on"], "dry": c["dry"], "pts": c["pts"],
        })
    return out


def daily_series(rows: List[Dict[str, Any]], cycles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    first_pre: Dict[int, float] = {}
    for c in cycles:
        first_pre.setdefault(c["day"], c["pre"])
    by_day: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        if not r.get("measurement_valid") or r.get("depth_to_water_m") is None:
            continue
        day = math.floor(r["_h"] / 24)
        d = float(r["depth_to_water_m"])
        e = by_day.setdefault(day, {"day": day, "first": d, "peak": d})
        e["peak"] = max(e["peak"], d)
    out = []
    for day in sorted(by_day):
        e = by_day[day]
        swl = first_pre.get(day, e["first"])
        out.append({"day": day, "swl": swl, "peak": max(e["peak"], swl)})
    return out


# ---------------------------------------------------------------- forecast
def forecast(daily: List[Dict[str, Any]], cycles: List[Dict[str, Any]], well: Dict[str, Any], day: int,
             sensor_fault: bool) -> Dict[str, Any]:
    swl_now = daily[-1]["swl"] if daily else math.nan
    D = max(0.5, median([c["s_end"] for c in cycles[-4:]]) if cycles else 0.5) + 0.4
    if not math.isfinite(D):
        D = 0.9
    limit = float(well["intake_m"]) - float(well.get("min_submergence_m", 2.0))  # threshold depth
    fc: Dict[str, Any] = {"swl": swl_now, "D": D, "limit": limit}
    rg = regress([(e["day"], e["swl"]) for e in daily[-21:]])
    fc["rate"] = rg["m"] if rg else math.nan
    if sensor_fault:
        fc["state"] = "paused"
    elif day >= MONSOON_ONSET_DAY:
        fc["state"] = "monsoon"
    elif not rg or len(daily) < 5:
        fc["state"] = "learning"
    else:
        remaining = limit - D - swl_now
        fc["remaining"] = remaining
        m, se = rg["m"], rg["se"]
        if remaining <= 0:
            fc.update(state="dry", p10=day, p50=day, p90=day)
        elif m < 0.03:
            fc.update(state="stable", margin=remaining)
        else:
            fc["p50"] = day + remaining / m
            fc["p10"] = day + max(0, remaining - 0.15 * D) / (m + 1.28 * se + 0.005)
            fc["p90"] = day + (remaining + 0.15 * D) / max(m - 1.28 * se, 0.02)
            fc["marginOnset"] = remaining - m * (MONSOON_ONSET_DAY - day)
            if fc["p50"] < MONSOON_ONSET_DAY:
                need = remaining / (MONSOON_ONSET_DAY - day)
                pump_part = max(m - 0.03, 0.01)
                fc["state"] = "fail"
                fc["cut"] = int(min(90, max(5, math.ceil((1 - (need - 0.03) / pump_part) * 20) * 5)))
            else:
                fc["state"] = "ok"
    return fc


# ---------------------------------------------------------------- interference
def interference_hits(rows: List[Dict[str, Any]]) -> List[float]:
    """Level falls > 45 cm while our pump has been off for more than 2.5 h."""
    hits: List[float] = []
    last_off: Optional[float] = None
    win_off: Optional[float] = None
    win_min = math.inf
    win_hit = False
    prev_on = False
    for r in rows:
        on = r["pump_state"] == "ON"
        if prev_on and not on:
            last_off = r["_h"]
        prev_on = on
        if on or last_off is None or not r.get("measurement_valid") or r.get("depth_to_water_m") is None:
            continue
        if r["_h"] - last_off < 2.5:
            continue
        v = float(r["depth_to_water_m"])
        if win_off != last_off:
            win_off, win_min, win_hit = last_off, v, False
        else:
            win_min = min(win_min, v)
            if not win_hit and v - win_min > 0.45:
                win_hit = True
                hits.append(r["_h"])
    return hits


# ---------------------------------------------------------------- main entry
def baseline_cycles(readings: List[Dict[str, Any]], flow_m3_day: float) -> List[Dict[str, Any]]:
    """Pump cycles from a well's first days of data: its commissioning baseline for slow faults."""
    rows = sorted((dict(r) for r in readings if not r.get("stale") and r.get("pump_state") in ("ON", "OFF")),
                  key=lambda r: parse_ts(r["timestamp"]))
    if not rows:
        return []
    season = season_start_for(parse_ts(rows[0]["timestamp"]))
    for r in rows:
        r["_ts"] = parse_ts(r["timestamp"])
        r["_h"] = (r["_ts"] - season).total_seconds() / 3600
    cyc = split_cycles(rows, flow_m3_day)
    if not cyc:
        return []
    first = cyc[0]["day"]
    return [c for c in cyc if c["day"] < first + 10 and not c["dry"] and c["s_end"] > 0.3]


def analyze(readings: List[Dict[str, Any]], well: Optional[Dict[str, Any]] = None,
            baseline: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Full analysis for one well. `readings` may be in any order.
    `baseline` (optional): readings from the well's first days of data. Slow faults (clogging, pump wear,
    a dewatered fracture) are then judged against that fixed baseline instead of a sliding one, so a warning
    stays up for as long as the fault lasts.
    """
    well = {**DEFAULT_WELL, **(well or {})}
    if not readings:
        return {"well": well, "status": "no_data", "findings": [], "forecast": {"state": "learning"}, "daily": [], "cycles": [], "readings": []}

    all_rows = sorted((dict(r) for r in readings), key=lambda r: parse_ts(r["timestamp"]))
    # Stale readings and readings with an unknown pump state never feed the forecast.
    excluded = {"stale": sum(1 for r in all_rows if r.get("stale")),
                "unknown_pump_state": sum(1 for r in all_rows if r.get("pump_state") == "UNKNOWN")}
    rows = [r for r in all_rows if not r.get("stale") and r.get("pump_state") in ("ON", "OFF")] or all_rows[-1:]
    latest_ts = parse_ts(rows[-1]["timestamp"])
    season = season_start_for(latest_ts)
    for r in rows:
        r["_ts"] = parse_ts(r["timestamp"])
        r["_h"] = (r["_ts"] - season).total_seconds() / 3600
    now_h = rows[-1]["_h"]
    day = math.floor(now_h / 24)

    flow = float(well["pump_flow_m3_day"])
    cycles = split_cycles(rows, flow)
    daily = daily_series(rows, cycles)

    recent_all = [c for c in cycles if c["day"] > day - 3 and not c["dry"]]
    recent = [c for c in cycles if c["day"] > day - 4 and not c["dry"] and c["s_end"] > 0.3]
    older = [c for c in cycles if day - 20 < c["day"] <= day - 10 and not c["dry"] and c["s_end"] > 0.3]
    sensor_fault = len(recent_all) >= 2 and all(abs(c["s_end"]) < 0.08 and c["run"] > 0.4 for c in recent_all[-2:])
    fc = forecast(daily, cycles, well, day, sensor_fault)
    swl_now = fc["swl"]

    F: List[Dict[str, Any]] = []
    # Dry running: the relay cut the pump, or the motor is drawing less current while running.
    last_dry = next((c for c in reversed(cycles) if c["dry"]), None)
    if last_dry and now_h - last_dry["t_off"] < 36:
        when = season + dt.timedelta(hours=last_dry["t_off"])
        F.append({"sev": "crit", "title": "Pump cut off: water at intake",
                  "detail": f"Water reached {well['intake_m']:g} m at {fmt_hm(when)} on {fmt_day(season, last_dry['t_off'] / 24)}.",
                  "msg": "dry", "v": {"time": fmt_hm(when)}})
    elif rows[-1]["pump_state"] == "ON" and rows[-1].get("pump_current_a"):
        normal_i = median([c["I"] for c in cycles[-10:] if c["I"] > 0])
        if math.isfinite(normal_i) and float(rows[-1]["pump_current_a"]) < 0.75 * normal_i:
            F.append({"sev": "crit", "title": "Pump running dry",
                      "detail": f"Motor current {float(rows[-1]['pump_current_a']):.1f} A against a normal {normal_i:.1f} A.",
                      "msg": "dryon", "v": {"time": fmt_hm(latest_ts)}})

    if sensor_fault:
        F.append({"sev": "fault", "title": "Depth reading not responding",
                  "detail": f"The last runs moved the reading less than 8 cm. Likely a false echo from a pipe joint near {recent_all[-1]['pre']:.0f} m.",
                  "msg": "sensor", "v": {}})
    else:
        tR = ratio(median([c["T"] for c in recent]), median([c["T"] for c in older]))
        scR = ratio(median([c["SC"] for c in recent]), median([c["SC"] for c in older]))
        sR = ratio(median([c["s_end"] for c in recent]), median([c["s_end"] for c in older]))
        iR = ratio(median([c["I"] for c in recent]), median([c["I"] for c in older]))
        big_dd = median([c["s_end"] for c in recent]) > 2.2  # ratios need measurable drawdown
        swl_old = next((e["swl"] for e in daily if e["day"] == day - 10), swl_now)
        fractures = well.get("fractures") or []
        crossed = any(swl_old - 2 <= f["d"] <= swl_now + 2 for f in fractures) if fractures else (swl_now - swl_old) > 2

        if big_dd and math.isfinite(tR) and tR < 0.65 and crossed and scR >= tR * 0.8:
            known = sorted((f for f in fractures if f["d"] <= swl_now + 1), key=lambda f: -f["d"])
            dep = known[0]["d"] if known else round(swl_now)
            F.append({"sev": "act", "title": f"Fracture dewatered at {dep:g} m",
                      "detail": f"Transmissivity fell {round((1 - tR) * 100)}% in a week as the water table dropped past a water-bearing fracture.",
                      "msg": "fracture", "v": {"depth": dep}})

        fixed = baseline_cycles(baseline, flow) if baseline else []
        if len(fixed) >= 3:
            base, base_age = fixed, 99  # commissioning baseline: old enough by definition
        else:
            base = [c for c in cycles if c["day"] < cycles[0]["day"] + 10 and not c["dry"] and c["s_end"] > 0.3] if cycles else []
            base_age = day - cycles[0]["day"] if cycles else 0
        scB = ratio(median([c["SC"] for c in recent]), median([c["SC"] for c in base]))
        tB = ratio(median([c["T"] for c in recent]), median([c["T"] for c in base]))
        sB = ratio(median([c["s_end"] for c in recent]), median([c["s_end"] for c in base]))
        iB = ratio(median([c["I"] for c in recent]), median([c["I"] for c in base]))
        swl_base = median([c["pre"] for c in base]) if base else swl_now
        # A dewatered fracture stays dewatered: also compare with the baseline, not only with last week.
        crossed_b = any(min(swl_base, swl_now) - 2 <= f["d"] <= max(swl_base, swl_now) + 2 for f in fractures) if fractures else False
        if (not any(f["title"].startswith("Fracture") for f in F) and fixed and big_dd and math.isfinite(tB)
                and tB < 0.65 and crossed_b and scB >= tB * 0.8):
            known = sorted((f for f in fractures if f["d"] <= swl_now + 1), key=lambda f: -f["d"])
            dep = known[0]["d"] if known else round(swl_now)
            F.append({"sev": "act", "title": f"Fracture dewatered at {dep:g} m",
                      "detail": f"Transmissivity is {round((1 - tB) * 100)}% below this well's baseline since the water table dropped past a water-bearing fracture.",
                      "msg": "fracture", "v": {"depth": dep}})
        if big_dd and math.isfinite(scB) and math.isfinite(tB) and base_age > 20 and scB < tB * 0.78:
            pc = round((tB / scB - 1) * 100)
            F.append({"sev": "act", "title": "Well clogging, aquifer unchanged",
                      "detail": f"Drawdown per run is up {pc}% more than the aquifer explains, while the refill slope holds. The loss is at the well face.",
                      "msg": "clog", "v": {"pct": pc}})

        wear_vs_week = math.isfinite(iR) and iR < 0.97 and math.isfinite(sR) and sR < 0.88
        wear_vs_base = bool(fixed) and math.isfinite(iB) and iB < 0.97 and math.isfinite(sB) and sB < 0.88
        if big_dd and (wear_vs_week or wear_vs_base):
            if wear_vs_base and not wear_vs_week:
                sR, iR = sB, iB
            F.append({"sev": "watch", "title": "Pump delivering less water",
                      "detail": f"Drawdown per run down {round((1 - sR) * 100)}%, motor current down {round((1 - iR) * 100)}%. Aquifer looks unchanged.",
                      "msg": "wear", "v": {"pct": round((1 - sR) * 100)}})

        ie = [h for h in interference_hits(rows) if h > now_h - 5 * 24]
        if len(ie) >= 2:
            when = season + dt.timedelta(hours=ie[-1])
            F.append({"sev": "watch", "title": "Level drops while your pump is off",
                      "detail": f"{len(ie)} drops of more than 45 cm in 5 days, around {fmt_hm(when)}. A nearby borewell shares the aquifer.",
                      "msg": "interf", "v": {"time": fmt_hm(when)}})

        # Weak monsoon needs daily rainfall for the well's location (IMD grid), stored on the well record.
        rain = well.get("rain_mm") or {}
        if rain and 267 <= day <= 364:
            act = nor = 0.0
            for d in range(243, day + 1):
                date = (season + dt.timedelta(days=d)).date()
                act += float(rain.get(date.isoformat(), 0.0))
                nor += RAIN_MEAN_MM[date.month - 1] / 30.4
            pct = round(act / nor * 100) if nor else 100
            if pct < 65:
                F.append({"sev": "act", "title": "Weak monsoon recharge",
                          "detail": f"Rain since 1 Jun is {pct}% of normal. Water table back only to {swl_now:.1f} m.",
                          "msg": "weak", "v": {"pct": pct, "swl": f"{swl_now:.1f}"}})

        if fc["state"] == "fail":
            F.append({"sev": "crit" if fc["p50"] - day < 21 else "act", "title": "Dry before the monsoon",
                      "detail": f"Likely dry around {fmt_day(season, fc['p50'])}. Cut pumping {fc['cut']}% to reach 10 Jun.",
                      "msg": "forecast", "v": {"rate": f"{fc['rate']:.2f}", "date": fc["p50"], "cut": fc["cut"]}})
        elif fc["state"] == "dry":
            F.append({"sev": "crit", "title": "No margin left", "detail": "Peak drawdown already reaches the intake. Shorten runs now.",
                      "msg": "forecast", "v": {"rate": f"{(fc['rate'] if math.isfinite(fc['rate']) else 0):.2f}", "date": day, "cut": 50}})
        elif fc["state"] == "ok" and fc["rate"] > 0.08:
            F.append({"sev": "watch", "title": "Seasonal decline",
                      "detail": f"Falling {fc['rate']:.2f} m/day. About {max(0, fc['marginOnset']):.0f} m to spare at the monsoon.",
                      "msg": "depl", "v": {"rate": f"{fc['rate']:.2f}", "margin": f"{max(0, fc['marginOnset']):.0f}"}})

    if not F:
        F.append({"sev": "ok", "title": "Healthy", "detail": "Refill and drawdown look normal for the season.", "msg": "ok",
                  "v": {"swl": f"{swl_now:.1f}" if math.isfinite(swl_now) else "—"}})
    F.sort(key=lambda f: -SEVERITY_RANK[f["sev"]])

    latest = {k: v for k, v in rows[-1].items() if not k.startswith("_")}
    last_valid = next((r for r in reversed(rows) if r.get("measurement_valid") and r.get("depth_to_water_m") is not None), None)
    return {
        "well": well,
        "status": "ok",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "season_start": season.isoformat(),
        "now_hours": round(now_h, 4),
        "latest": latest,
        "last_valid_depth_m": float(last_valid["depth_to_water_m"]) if last_valid else None,
        "water_table_m": r2(swl_now, 3),
        "threshold_m": round(float(well["intake_m"]) - float(well.get("min_submergence_m", 2.0)), 2),
        "excluded_readings": excluded,
        "data_quality": {"readings_used": len(rows), "readings_total": len(all_rows)},
        "findings": F,
        "forecast": {k: (r2(v, 4) if isinstance(v, float) else v) for k, v in fc.items()},
        "daily": [{"day": e["day"], "swl": round(e["swl"], 3), "peak": round(e["peak"], 3)} for e in daily],
        "cycles": [_cycle_out(c, i == len(cycles) - 1) for i, c in enumerate(cycles[-12:], start=len(cycles) - min(12, len(cycles)))],
        "readings": [
            {"h": round(r["_h"], 4), "d": r["depth_to_water_m"], "pump": r["pump_state"], "i": r.get("pump_current_a"), "valid": r.get("measurement_valid"),
             "temp": r.get("temperature_c"), "tau": r.get("echo_tau_ms")}
            for r in rows if r["_h"] >= now_h - 72
        ],
    }


def _cycle_out(c: Dict[str, Any], with_points: bool) -> Dict[str, Any]:
    out = {
        "t_on": round(c["t_on"], 4), "t_off": round(c["t_off"], 4), "day": c["day"], "pre": round(c["pre"], 3), "s_end": round(c["s_end"], 3),
        "T": r2(c["T"], 3), "slope": r2(c["slope"], 4), "intercept": r2(c["intercept"], 4), "SC": round(c["SC"], 2), "I": round(c["I"], 2),
        "run": round(c["run"], 3), "dry": c["dry"],
    }
    if with_points:
        out["pts"] = [[round(t, 4), round(d, 3)] for t, d in c["pts"]]
    return out
