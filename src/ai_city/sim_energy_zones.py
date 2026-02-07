from __future__ import annotations

import os
import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import simpy
import pandas as pd
import joblib


# -----------------------------
# Zone Configuration
# -----------------------------
@dataclass(frozen=True)
class ZoneConfig:
    name: str
    priority: int            # smaller = higher priority
    base_kw: float           # nominal base demand in kW
    flex_kw: float           # nominal flexible demand in kW (can be throttled)
    morning_peak_mult: float # e.g., 1.35 means +35% at morning peak
    evening_peak_mult: float # e.g., 1.55 means +55% at evening peak


# -----------------------------
# Energy Zone "Agent"
# -----------------------------
class EnergyZone:
    def __init__(self, cfg: ZoneConfig):
        self.cfg = cfg

        # current-tick requests (kW)
        self.request_kw: float = 0.0
        self.flex_request_kw: float = 0.0

        # current-tick served/unmet (kW)
        self.served_kw: float = 0.0
        self.unmet_kw: float = 0.0
        self.flex_served_kw: float = 0.0
        self.flex_unmet_kw: float = 0.0

    def compute_demand(self, hour: int) -> None:
        """
        Simple time-of-day curve:
        - Morning peak ~ 7-10
        - Evening peak ~ 17-21
        - Midday moderate
        - Late night low
        """
        # reset per tick
        self.served_kw = 0.0
        self.unmet_kw = 0.0
        self.flex_served_kw = 0.0
        self.flex_unmet_kw = 0.0

        # base multiplier by hour block
        base_mult = 1.0
        if 7 <= hour <= 10:
            base_mult *= self.cfg.morning_peak_mult
        elif 17 <= hour <= 21:
            base_mult *= self.cfg.evening_peak_mult
        elif 11 <= hour <= 16:
            base_mult *= 1.10
        elif 0 <= hour <= 5:
            base_mult *= 0.85

        # request base + flex
        self.request_kw = max(0.0, self.cfg.base_kw * base_mult)

        # flexible demand is present but can be throttled by the manager
        # (we also lightly reduce flex late-night to keep plots realistic)
        flex_mult = 1.0
        if 0 <= hour <= 5:
            flex_mult = 0.65
        self.flex_request_kw = max(0.0, self.cfg.flex_kw * flex_mult)


# -----------------------------
# Energy Manager (Allocator)
# -----------------------------
class EnergyManager:
    def __init__(
        self,
        env: simpy.Environment,
        zones: List[EnergyZone],
        capacity_kw: float,
        log_rows: List[Dict[str, Any]],
        forecast_model_path: Optional[str] = None,
    ):
        self.env = env
        self.zones = zones
        self.capacity_kw = float(capacity_kw)
        self.log_rows = log_rows

        # optional: predictive model for next-step demand forecasting
        self.forecast = None
        if forecast_model_path:
            self.forecast = joblib.load(forecast_model_path)

    def allocate(self, tick_s: int, start_hour: int) -> None:
        """
        Allocate capacity each tick:
        1) Serve BASE demand by priority (highest priority first)
        2) Use remaining capacity for FLEX demand, with demand-response throttling
           + optional forecast-aware clamping to reduce "wastage" near predicted peaks
        """
        hour = int((start_hour + (self.env.now / 3600.0)) % 24)

        # 1) update zone demands
        for z in self.zones:
            z.compute_demand(hour)

        # totals
        total_req = sum(z.request_kw for z in self.zones)
        total_flex_req = sum(z.flex_request_kw for z in self.zones)

        # Optional forecast: predict next-step total base demand
        pred_next_total_req_kw = None
        if self.forecast is not None:
            pack = self.forecast
            model = pack["model"]
            feature_cols = pack["features"]
            zone_list = pack["zones"]

            zone_map = {z.cfg.name: z for z in self.zones}

            feat = {
                "hour": hour,
                "hour_sin": math.sin(2 * math.pi * hour / 24.0),
                "hour_cos": math.cos(2 * math.pi * hour / 24.0),
                "total_req_kw": total_req,
            }

            # IMPORTANT: this loop is INSIDE the forecast block
            for zn in zone_list:
                feat[f"{zn}_req_kw"] = zone_map[zn].request_kw

            X = pd.DataFrame([feat])[feature_cols]
            pred_next_total_req_kw = float(model.predict(X)[0])

        # 2) Serve base demand by priority
        remaining = self.capacity_kw
        for z in sorted(self.zones, key=lambda zz: zz.cfg.priority):
            served = min(z.request_kw, remaining)
            z.served_kw = served
            z.unmet_kw = max(0.0, z.request_kw - served)
            remaining -= served

        total_served = sum(z.served_kw for z in self.zones)
        total_unmet = sum(z.unmet_kw for z in self.zones)

        # 3) Serve flexible demand with throttling
        off_peak = (hour < 7) or (hour >= 22)
        flex_budget = max(0.0, remaining)

        # demand response: reduce flex serving during peak hours
        if not off_peak:
            flex_budget *= 0.35

        # forecast-aware tightening (minimize energy "wastage" near predicted base peaks)
        if pred_next_total_req_kw is not None:
            headroom_next = self.capacity_kw - pred_next_total_req_kw
            if headroom_next < 0.10 * self.capacity_kw:
                flex_budget *= 0.10
            elif headroom_next < 0.25 * self.capacity_kw:
                flex_budget *= 0.35

        # allocate flex (priority order; flex is always after base)
        flex_remaining = flex_budget
        for z in sorted(self.zones, key=lambda zz: zz.cfg.priority):
            flex_served = min(z.flex_request_kw, flex_remaining)
            z.flex_served_kw = flex_served
            z.flex_unmet_kw = max(0.0, z.flex_request_kw - flex_served)
            flex_remaining -= flex_served

        total_flex_served = sum(z.flex_served_kw for z in self.zones)
        total_flex_unmet = sum(z.flex_unmet_kw for z in self.zones)

        # 4) log row
        row: Dict[str, Any] = {
            "t_s": int(self.env.now),
            "hour": hour,
            "pred_next_total_req_kw": pred_next_total_req_kw,
            "capacity_kw": self.capacity_kw,

            "total_req_kw": total_req,
            "total_served_kw": total_served,
            "total_unmet_kw": total_unmet,

            "total_flex_req_kw": total_flex_req,
            "total_flex_served_kw": total_flex_served,
            "total_flex_unmet_kw": total_flex_unmet,
        }

        for z in self.zones:
            zn = z.cfg.name
            row[f"{zn}_req_kw"] = z.request_kw
            row[f"{zn}_served_kw"] = z.served_kw
            row[f"{zn}_unmet_kw"] = z.unmet_kw

            row[f"{zn}_flex_req_kw"] = z.flex_request_kw
            row[f"{zn}_flex_served_kw"] = z.flex_served_kw
            row[f"{zn}_flex_unmet_kw"] = z.flex_unmet_kw

        self.log_rows.append(row)


# -----------------------------
# Sim process
# -----------------------------
def energy_process(env: simpy.Environment, mgr: EnergyManager, tick_s: int, start_hour: int):
    while True:
        mgr.allocate(tick_s=tick_s, start_hour=start_hour)
        yield env.timeout(tick_s)


# -----------------------------
# Run + Report
# -----------------------------
def run(
    sim_hours: int = 24,
    tick_s: int = 60,
    start_hour: int = 6,
    capacity_kw: float = 600.0,
    out_csv: str = r"runs\energy_zones_log.csv",
    use_forecast: bool = False,
    forecast_model_path: str = r"runs\energy_forecast_model.pkl",
):
    os.makedirs("runs", exist_ok=True)

    # Default zones (you can adjust, but keep names stable for the forecast trainer)
    cfgs = [
        ZoneConfig("hospital",     priority=1, base_kw=220, flex_kw=35, morning_peak_mult=1.10, evening_peak_mult=1.15),
        ZoneConfig("residential",  priority=3, base_kw=160, flex_kw=80, morning_peak_mult=1.25, evening_peak_mult=1.55),
        ZoneConfig("commercial",   priority=2, base_kw=140, flex_kw=65, morning_peak_mult=1.35, evening_peak_mult=1.20),
        ZoneConfig("industrial",   priority=4, base_kw=90,  flex_kw=55, morning_peak_mult=1.10, evening_peak_mult=1.10),
    ]
    zones = [EnergyZone(c) for c in cfgs]

    env = simpy.Environment()
    log_rows: List[Dict[str, Any]] = []

    mgr = EnergyManager(
        env,
        zones,
        capacity_kw=capacity_kw,
        log_rows=log_rows,
        forecast_model_path=(forecast_model_path if use_forecast else None),
    )

    env.process(energy_process(env, mgr, tick_s=tick_s, start_hour=start_hour))
    env.run(until=sim_hours * 3600)

    df = pd.DataFrame(log_rows)
    df.to_csv(out_csv, index=False)
    print(f"Saved energy log: {out_csv}")

    # Summary metrics (kWh)
    dt_h = tick_s / 3600.0
    served_kwh = float((df["total_served_kw"] * dt_h).sum())
    unmet_kwh = float((df["total_unmet_kw"] * dt_h).sum())
    flex_served_kwh = float((df["total_flex_served_kw"] * dt_h).sum())
    flex_unmet_kwh = float((df["total_flex_unmet_kw"] * dt_h).sum())

    peak_req = float(df["total_req_kw"].max())
    peak_served = float(df["total_served_kw"].max())

    print("\n=== Energy Summary ===")
    print(f"Peak requested (base) kW: {peak_req:.1f}")
    print(f"Peak served (base) kW:    {peak_served:.1f}")
    print(f"Total served (base) kWh:  {served_kwh:.2f}")
    print(f"Total unmet (base) kWh:   {unmet_kwh:.2f}")
    print(f"Total served (flex) kWh:  {flex_served_kwh:.2f}")
    print(f"Total unmet (flex) kWh:   {flex_unmet_kwh:.2f}")

    return out_csv


if __name__ == "__main__":
    # Allow forecast mode via env var (for easy grading + automation scripts)
    use_forecast_env = os.getenv("AI_CITY_USE_FORECAST") == "1"
    model_path = os.getenv("AI_CITY_FORECAST_MODEL", r"runs\energy_forecast_model.pkl")

    out_csv = r"runs\energy_zones_log_forecast.csv" if use_forecast_env else r"runs\energy_zones_log.csv"
    run(use_forecast=use_forecast_env, forecast_model_path=model_path, out_csv=out_csv)