"""
BoreWise virtual borewell (Python port of frontend/src/sim/simulator.js).

One physics model for the whole project, so the 3D app, the backend tests and the
telemetry fleet all agree:

* Cooper-Jacob drawdown with wellbore storage, superposed over recent pump runs
* well loss (skin) for clogging, impeller wear for pump degradation
* fracture-controlled transmissivity (fractures above the water table stop contributing)
* seasonal decline from pumping, monsoon recharge from synthetic Pune rainfall
* acoustic readings only while the pump is off (the sounding is gated)

Depth is metres below ground; bigger numbers mean less water. Depths are physically
bounded: water can never go below the bottom of the bore.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- constants
STORATIVITY = 3e-4
WELLBORE_TAU = 0.006  # days
MONSOON_ONSET_DAY = 252  # ~10 June, counted from 1 Oct
SEASON_DAYS = 365
STEP_HOURS = 1 / 30  # 2-minute resolution
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

RAIN_MEAN_MM = [1, 0, 2, 10, 25, 140, 190, 130, 120, 75, 25, 5]
RAIN_WET_PROB = [0.03, 0.02, 0.05, 0.12, 0.2, 0.55, 0.75, 0.65, 0.5, 0.25, 0.1, 0.04]

NORMAL_FRACTURES = [{"d": 22, "T": 8}, {"d": 48, "T": 5}, {"d": 76, "T": 10}, {"d": 98, "T": 9}]

BASE_SCENARIO: Dict[str, Any] = {
    "Q": 172.8, "matrixT": 2, "fr": NORMAL_FRACTURES, "swl0": 18, "startDay": 0, "sched": [6, 18],
    "run": 1, "depth": 120, "intake": 103, "rainF": 1, "seed": 11,
}

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "healthy": {"name": "Healthy season", "warm_days": 60},
    "overpump": {"name": "Over-pumping", "sched": [6, 13, 20], "run": 2, "warm_days": 100},
    "fracture": {"name": "Fracture dewatering", "fr": [{"d": 22, "T": 4}, {"d": 48, "T": 22}, {"d": 76, "T": 4}, {"d": 98, "T": 4}],
                 "run": 1.5, "warm_until_swl": 43.5, "warm_max": 230},
    "interf": {"name": "Neighbour interference", "neigh": {"Q": 400, "r": 30, "times": [9.5, 21.5], "run": 2}, "warm_days": 40},
    "clog": {"name": "Well clogging", "skinRate": 0.1, "skinStart": 31, "warm_days": 46},
    "weak": {"name": "Weak monsoon", "rainF": 0.45, "run": 1.5, "warm_days": 244},
    "wear": {"name": "Pump wear", "wearRate": 0.01, "wearStart": 24, "warm_days": 40},
    "dry": {"name": "Dry running", "startDay": 151, "swl0": 85, "run": 2.5, "warm_days": 0.4},
    "sensor": {"name": "Sensor fault", "falseEcho": {"d": 21, "start": 55}, "warm_days": 52},
    # Slow refill from a tight aquifer (the teammate's original 'weak_recharge' idea).
    "weak_recharge": {"name": "Weak recharge (tight aquifer)", "matrixT": 0.6,
                      "fr": [{"d": 22, "T": 2.5}, {"d": 48, "T": 1.5}, {"d": 76, "T": 3}, {"d": 98, "T": 2.5}], "run": 1.5, "warm_days": 30},
}
SCENARIO_ALIASES = {"normal": "healthy", "over_pumping": "overpump"}

BORES: Dict[str, Dict[str, Any]] = {
    "open": {"name": "Open-hole borewell", "depth": 120, "intake": 103, "Q": 172.8, "pump": "sub", "r": 0.2, "rw": 0.075, "dryOff": 18},
    "screen": {"name": "Screened tubewell", "depth": 120, "intake": 100, "Q": 216, "pump": "sub", "r": 0.24, "rw": 0.12, "skin0": -0.8, "dryOff": 16},
    "dug": {"name": "Dug-cum-bore well", "depth": 110, "intake": 95, "Q": 259.2, "pump": "sub", "r": 0.2, "rw": 0.075, "dug": {"d": 14, "R": 0.95}, "dryOff": 22},
    "hand": {"name": "Hand-pump borewell", "depth": 80, "intake": 46, "Q": 24, "pump": "hand", "r": 0.16, "rw": 0.075,
             "sched": [6, 7.5, 9, 11, 13, 16, 17.5, 19], "run": 0.4, "dryOff": 1.8},
}


def mulberry32(seed: int):
    """Same PRNG as the frontend so rainfall matches the 3D app exactly."""
    state = [seed & 0xFFFFFFFF]

    def nxt() -> float:
        a = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        state[0] = a
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


# ---------------------------------------------------------------- calendar
def season_start_for(when: dt.datetime) -> dt.datetime:
    """1 October (IST) of the hydrological season that `when` falls in."""
    local = when.astimezone(IST)
    year = local.year if local.month >= 10 else local.year - 1
    return dt.datetime(year, 10, 1, tzinfo=IST)


DEFAULT_SEASON_START = dt.datetime(2026, 10, 1, tzinfo=IST)


def month_of_day(day: float, season_start: dt.datetime = DEFAULT_SEASON_START) -> int:
    return (season_start + dt.timedelta(days=day)).month - 1


def generate_rain(seed: int, monsoon_factor: float = 1.0, season_start: dt.datetime = DEFAULT_SEASON_START) -> List[float]:
    r = mulberry32(seed)
    out = []
    for d in range(366):
        m = month_of_day(d + 0.5, season_start)
        p = RAIN_WET_PROB[m]
        mm = 0.0
        if r() < p:
            mm = RAIN_MEAN_MM[m] / (30.4 * p) * -math.log(1 - r() + 1e-9)
        if 5 <= m <= 8:
            mm *= monsoon_factor
        out.append(mm)
    return out


def normal_rain_for_day(day: int, season_start: dt.datetime = DEFAULT_SEASON_START) -> float:
    return RAIN_MEAN_MM[month_of_day(day + 0.5, season_start)] / 30.4


# ---------------------------------------------------------------- config
def build_config(scenario: str = "healthy", bore: str = "open", **overrides: Any) -> Dict[str, Any]:
    """Merge base + scenario + bore type into one simulator config (mirrors applyBore in JS)."""
    scenario = SCENARIO_ALIASES.get(scenario, scenario)
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from {sorted(SCENARIOS) + sorted(SCENARIO_ALIASES)}")
    if bore not in BORES:
        raise ValueError(f"Unknown bore type '{bore}'. Choose from {sorted(BORES)}")
    sc = {**BASE_SCENARIO, **SCENARIOS[scenario], "id": scenario}
    b = BORES[bore]
    sc.update({
        "bore": bore, "bore_name": b["name"], "depth": b["depth"], "intake": b["intake"], "Q": b["Q"], "pumpKind": b["pump"],
        "skin0": b.get("skin0", 0.0), "dug": b.get("dug"), "rw": b.get("rw", 0.075),
        "fr": [f for f in sc["fr"] if f["d"] < b["depth"] - 4],
    })
    if "sched" in b:
        sc["sched"], sc["run"] = b["sched"], b["run"]
    sc["swl0"] = b["intake"] - b["dryOff"] if scenario == "dry" else min(sc["swl0"], b["intake"] - 20)
    sc.update(overrides)
    return sc


# ---------------------------------------------------------------- hydraulics
def transmissivity_at(swl: float, sc: Dict[str, Any]) -> float:
    T = sc["matrixT"]
    for f in sc["fr"]:
        T += f["T"] / (1 + math.exp(-(f["d"] - swl) / 1.2))
    return T


def _well_fn(tau: float, T: float, rw: float) -> float:
    if tau <= 0:
        return 0.0
    return math.log(1 + 2.25 * T * tau / (rw * rw * STORATIVITY)) * (1 - math.exp(-tau / WELLBORE_TAU))


def _dist_fn(tau: float, T: float, r: float) -> float:
    if tau <= 0:
        return 0.0
    return math.log(1 + 2.25 * T * tau / (r * r * STORATIVITY))


@dataclass
class PumpEvent:
    on: float
    Q: float
    skin: float
    off: Optional[float] = None
    i_sum: float = 0.0
    i_hours: float = 0.0


@dataclass
class Borewell:
    """Stateful virtual borewell. `t` is hours since the season start (1 Oct)."""

    sc: Dict[str, Any]
    season_start: dt.datetime = DEFAULT_SEASON_START
    seed: int = 4242
    t: float = 0.0
    swl: float = 0.0
    dl: float = 0.0
    skin: float = 0.0
    Q: float = 0.0
    run_scale: float = 1.0
    pump_on: bool = False
    auto: bool = True
    protect: bool = True
    dry_run: bool = False
    temp: float = 27.0
    current_a: float = 0.0
    T: float = 0.0
    events: List[PumpEvent] = field(default_factory=list)
    rain: List[float] = field(default_factory=list)
    next_on: float = 0.0
    last_off: Optional[float] = None
    log: List[str] = field(default_factory=list)
    just_cut_off: bool = False

    def __post_init__(self) -> None:
        sc = self.sc
        self.rng = random.Random(self.seed)
        self.t = sc["startDay"] * 24
        self.swl = self.dl = float(sc["swl0"])
        self.skin = sc.get("skin0", 0.0)
        self.Q = sc["Q"]
        self.T = transmissivity_at(self.swl, sc)
        self.rain = generate_rain(sc["seed"], sc["rainF"], self.season_start)
        self.temp = 27.5 + 3.5 * math.cos(2 * math.pi * (self.t / 24 - 226) / 365)
        self.next_on = self._next_start(self.t)

    # ---- schedule
    def _next_start(self, t: float) -> float:
        best = math.inf
        d0 = math.floor(t / 24)
        for d in (d0, d0 + 1):
            for h in self.sc["sched"]:
                x = d * 24 + h
                if t + 1e-6 < x < best:
                    best = x
        return best

    def timestamp(self, hours: Optional[float] = None) -> dt.datetime:
        return self.season_start + dt.timedelta(hours=self.t if hours is None else hours)

    # ---- pump
    def start_pump(self) -> None:
        self.events.append(PumpEvent(on=self.t, Q=self.Q, skin=self.skin))
        if len(self.events) > 4:
            self.events.pop(0)
        self.pump_on = True

    def stop_pump(self, dry: bool = False) -> None:
        if not self.pump_on:
            return
        self.pump_on = False
        self.events[-1].off = self.t
        self.last_off = self.t
        if dry:
            self.just_cut_off = True
            self.log.append(f"{self.timestamp():%d %b %H:%M} water at intake, pump cut off")

    # ---- drawdown
    def _own_drawdown(self, T: float) -> float:
        rw = self.sc.get("rw", 0.075)
        td = self.t / 24
        tot = 0.0
        for e in self.events:
            A = e.Q / (4 * math.pi * T)
            on = e.on / 24
            tot += A * _well_fn(td - on, T, rw)
            if e.off is not None:
                tot -= A * _well_fn(td - e.off / 24, T, rw)
            B = e.Q / (2 * math.pi * T) * e.skin
            if B > 0:
                if e.off is None:
                    tot += B * (1 - math.exp(-(td - on) / WELLBORE_TAU))
                else:
                    tot += B * (1 - math.exp(-(e.off - e.on) / 24 / WELLBORE_TAU)) * math.exp(-(td - e.off / 24) / WELLBORE_TAU)
        return tot

    def _neighbour_on(self) -> bool:
        n = self.sc.get("neigh")
        if not n:
            return False
        h = self.t % 24
        return any(x <= h < x + n["run"] for x in n["times"])

    def _neighbour_drawdown(self, T: float) -> float:
        n = self.sc.get("neigh")
        if not n:
            return 0.0
        A = n["Q"] / (4 * math.pi * T)
        d0 = math.floor(self.t / 24)
        tot = 0.0
        for d in (d0 - 1, d0):
            for h in n["times"]:
                on = d * 24 + h
                off = on + n["run"]
                if self.t > on:
                    tot += A * _dist_fn((self.t - on) / 24, T, n["r"])
                    if self.t > off:
                        tot -= A * _dist_fn((self.t - off) / 24, T, n["r"])
        return tot

    # ---- step
    def step(self, dt_h: float = STEP_HOURS) -> None:
        sc = self.sc
        self.just_cut_off = False
        self.t += dt_h
        day = math.floor(self.t / 24)
        if not self.pump_on and self.t >= self.next_on:
            self.next_on = self._next_start(self.t)
            if self.auto:
                self.start_pump()
        if self.pump_on and self.t >= self.events[-1].on + sc["run"] * self.run_scale:
            self.stop_pump(False)

        dd = dt_h / 24
        if sc.get("skinRate") and day >= sc["skinStart"]:
            self.skin += sc["skinRate"] * dd
        if sc.get("wearRate") and day >= sc["wearStart"]:
            self.Q *= 1 - sc["wearRate"] * dd

        T = transmissivity_at(self.swl, sc)
        self.T = T
        qn = sc["neigh"]["Q"] if self._neighbour_on() else 0.0
        rain = self.rain[min(day, 365)] if day >= 0 else 0.0
        recharge = min(1.0, max(0.15, (self.swl - 5) / 15))
        self.swl += (0.03 + 0.0089 * (self.Q if self.pump_on else 0) + 0.0015 * qn) * dd - rain * 0.09 * recharge * dd
        self.swl = max(5.0, min(self.swl, sc["depth"] - 1))

        own = self._own_drawdown(T)
        if sc.get("dug") and self.swl < sc["dug"]["d"]:
            own *= 0.15
        level = self.swl + own + self._neighbour_drawdown(T)

        self.dry_run = False
        if self.pump_on and level >= sc["intake"] - 0.3:
            self.dry_run = True
            level = min(level, sc["intake"] + 0.4)
            if self.protect:
                self.stop_pump(True)
        self.dl = min(level, sc["depth"] - 1)  # water cannot go below the bottom of the bore
        self.temp = 27.5 + 3.5 * math.cos(2 * math.pi * (self.t / 24 - 226) / 365)
        if self.pump_on and sc["pumpKind"] != "hand":
            self.current_a = 5.6 * (0.68 + 0.32 * self.Q / sc["Q"]) * (0.62 if self.dry_run else 1)
        else:
            self.current_a = 0.0
        if self.pump_on:
            self.events[-1].i_sum += self.current_a * dt_h
            self.events[-1].i_hours += dt_h

    def warm_up(self) -> None:
        sc = self.sc
        if "warm_until_swl" in sc:
            end = (sc["startDay"] + sc["warm_max"]) * 24
            while self.swl < sc["warm_until_swl"] and self.t < end:
                self.step()
        else:
            end = (sc["startDay"] + sc.get("warm_days", 0)) * 24
            while self.t < end:
                self.step()

    # ---- sensing
    def measured_depth(self) -> float:
        fe = self.sc.get("falseEcho")
        d = self.dl
        if fe and self.t / 24 >= fe["start"] and self.dl > fe["d"]:
            d = fe["d"]  # a pipe joint echo masks the water
        return d + self.rng.gauss(0, 0.025)

    def echo_tau_ms(self, depth: float) -> float:
        c = (331.3 + 0.606 * self.temp) * (1 - 0.0082)
        return 2 * depth / c * 1000
