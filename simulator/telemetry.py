"""
Turns the virtual borewell into the exact telemetry stream the ESP32 sends.

Device protocol (what real hardware does, so the backend sees identical data):
* every 15 minutes: a heartbeat reading
* pump switches ON  : an event record straight away (no depth: sounding is gated while pumping)
* pump switches OFF : an event record, then a valid reading every 2 minutes for the first hour
  of refill, which is what the recovery fit needs
* dry-run relay trips: the OFF record carries event = "dry_cutoff"
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterator, List, Optional

from .physics import STEP_HOURS, Borewell, build_config

FIRMWARE_TAG = "sim-0.4.0"


def _iso(ts: dt.datetime) -> str:
    return ts.isoformat(timespec="seconds")


def make_record(well: Borewell, well_id: str, data_source: str, event: Optional[str] = None,
                run_minutes: float = 0.0) -> Dict[str, Any]:
    valid = not well.pump_on
    depth = round(well.measured_depth(), 3) if valid else None
    rec: Dict[str, Any] = {
        "well_id": well_id,
        "timestamp": _iso(well.timestamp()),
        "data_source": data_source,
        "depth_to_water_m": depth,
        "temperature_c": round(well.temp, 2),
        "pump_state": "ON" if well.pump_on else "OFF",
        "pump_run_minutes": round(run_minutes, 1),
        "pump_current_a": round(well.current_a, 2),
        "measurement_valid": valid,
        "echo_tau_ms": round(well.echo_tau_ms(depth), 2) if depth is not None else None,
        "fw": FIRMWARE_TAG,
    }
    if event:
        rec["event"] = event
    return rec


def stream(well: Borewell, well_id: str, hours: float, data_source: str = "simulated") -> Iterator[Dict[str, Any]]:
    """Advance the well by `hours` and yield telemetry records in time order (one per timestamp)."""
    end = well.t + hours
    next_beat = (int(well.t * 4) + 1) / 4  # next 15-minute boundary
    next_refill: Optional[float] = None
    last_ts = None
    on_since: Optional[float] = None
    was_on = well.pump_on
    while well.t < end - 1e-9:
        well.step(STEP_HOURS)
        rec = None
        if well.pump_on and not was_on:
            on_since = well.t
            rec = make_record(well, well_id, data_source, "pump_on", 0)
        elif was_on and not well.pump_on:
            run = (well.t - (on_since if on_since is not None else well.t)) * 60
            rec = make_record(well, well_id, data_source, "dry_cutoff" if well.just_cut_off else "pump_off", run)
            next_refill = well.t + 2 / 60
        elif next_refill is not None and not well.pump_on and well.t >= next_refill - 1e-9:
            rec = make_record(well, well_id, data_source)
            next_refill = next_refill + 2 / 60 if well.last_off is not None and well.t - well.last_off < 1 else None
        elif well.t >= next_beat - 1e-9:
            run = (well.t - on_since) * 60 if well.pump_on and on_since is not None else 0
            rec = make_record(well, well_id, data_source, None, run)
        if well.t >= next_beat - 1e-9:
            next_beat += 0.25
        was_on = well.pump_on
        if rec and rec["timestamp"] != last_ts:
            last_ts = rec["timestamp"]
            yield rec


def scenario_readings(scenario: str = "overpump", bore: str = "open", days: float = 30, well_id: str = "BW-001",
                      data_source: str = "simulated", seed: int = 4242) -> List[Dict[str, Any]]:
    """Warm the scenario to its interesting moment minus `days`, then return `days` of telemetry."""
    sc = build_config(scenario, bore)
    well = Borewell(sc, seed=seed)
    target_day = _warm_target_day(well)
    # Start `days` earlier so the stream ends where the 3D app's scenario begins.
    start_day = max(sc["startDay"], target_day - days)
    while well.t < start_day * 24:
        well.step()
    return list(stream(well, well_id, (target_day - start_day) * 24 if target_day > start_day else days * 24, data_source))


def _warm_target_day(well: Borewell) -> float:
    """Season day at which the scenario's warm-up ends (computed on a throwaway copy)."""
    probe = Borewell(dict(well.sc), seed=well.seed)
    probe.warm_up()
    return probe.t / 24
