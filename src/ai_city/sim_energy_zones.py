import simpy
import random
import math
import pandas as pd
from dataclasses import dataclass


# -----------------------------
# Energy demand model
# -----------------------------

@dataclass
class EnergyZoneConfig:
    name: str
    base_kw: float              # constant baseline
    peak_kw: float              # extra peak amplitude
    priority: int               # lower number = higher priority (1 = critical)
    flexible_kw: float = 0.0    # optional flexible load that can be served when capacity allows


def time_of_day_hour(sim_s: float, start_hour: float = 6.0) -> float:
    """Convert simulation seconds -> hour of day (float), assuming sim time is real time."""
    return (start_hour + sim_s / 3600.0) % 24.0


def demand_curve_kw(cfg: EnergyZoneConfig, hour: float) -> float:
    """
    Smooth demand curve with a morning bump and an evening bump.
    (Simple + stable for a project; easy to explain in report.)
    """
    # morning peak around 8-9
    morning = math.exp(-0.5 * ((hour - 8.5) / 1.2) ** 2)
    # evening peak around 19
    evening = math.exp(-0.5 * ((hour - 19.0) / 1.7) ** 2)

    # base + peak contribution
    base = cfg.base_kw
    peak = cfg.peak_kw * (0.7 * morning + 1.0 * evening)

    # small noise
    noise = random.uniform(-0.05, 0.05) * (base + peak)

    return max(0.0, base + peak + noise)


# -----------------------------
# Agents
# -----------------------------

class EnergyZone:
    def __init__(self, env: simpy.Environment, cfg: EnergyZoneConfig):
        self.env = env
        self.cfg = cfg

        self.request_kw = 0.0
        self.served_kw = 0.0
        self.unmet_kw = 0.0

        # flexible load (served only if spare capacity)
        self.flex_request_kw = cfg.flexible_kw
        self.flex_served_kw = 0.0
        self.flex_unmet_kw = 0.0

    def compute_requests(self, hour: float):
        self.request_kw = demand_curve_kw(self.cfg, hour)
        self.flex_request_kw = self.cfg.flexible_kw  # constant flexible load request (simple)

    def apply_allocation(self, served_kw: float, served_flex_kw: float):
        self.served_kw = served_kw
        self.unmet_kw = max(0.0, self.request_kw - served_kw)

        self.flex_served_kw = served_flex_kw
        self.flex_unmet_kw = max(0.0, self.flex_request_kw - served_flex_kw)


class EnergyManager:
    """
    Rule-based allocator:
      1) Serve base demands by priority (critical zones first)
      2) Use remaining capacity for flexible loads (off-peak favored)
      3) Track peak + unmet + total energy served
    """
    def __init__(self, env: simpy.Environment, zones: list[EnergyZone], capacity_kw: float, log_rows: list):
        self.env = env
        self.zones = zones
        self.capacity_kw = capacity_kw
        self.log_rows = log_rows

        # metrics
        self.peak_requested_kw = 0.0
        self.peak_served_kw = 0.0
        self.total_served_kwh = 0.0
        self.total_unmet_kwh = 0.0
        self.total_flex_served_kwh = 0.0
        self.total_flex_unmet_kwh = 0.0

    def allocate(self, tick_s: int, start_hour: float):
        hour = time_of_day_hour(self.env.now, start_hour=start_hour)

        # 1) zones compute their requests at this tick
        for z in self.zones:
            z.compute_requests(hour)

        total_req = sum(z.request_kw for z in self.zones)
        total_flex_req = sum(z.flex_request_kw for z in self.zones)

        self.peak_requested_kw = max(self.peak_requested_kw, total_req + total_flex_req)

        remaining = self.capacity_kw

        # 2) Serve BASE demand by priority first
        zones_by_priority = sorted(self.zones, key=lambda z: z.cfg.priority)
        for z in zones_by_priority:
            base_served = min(z.request_kw, remaining)
            remaining -= base_served

            # placeholder: flexible served later
            z.apply_allocation(served_kw=base_served, served_flex_kw=0.0)

        # 3) Serve FLEX loads only if capacity remains; bias to off-peak hours
        # Off-peak definition (simple): before 7am or after 10pm
        off_peak = (hour < 7.0) or (hour >= 22.0)
        flex_budget = remaining

        # if on-peak, restrict flexible usage (simulate “demand response”)
        if not off_peak:
            flex_budget *= 0.35  # only allow 35% of leftover for flexible on-peak

        # allocate flex by priority too (or you can invert priority if you want)
        for z in zones_by_priority:
            if flex_budget <= 0:
                break
            flex_served = min(z.flex_request_kw, flex_budget)
            flex_budget -= flex_served

            # update allocation (base already set)
            z.apply_allocation(served_kw=z.served_kw, served_flex_kw=flex_served)

        total_served = sum(z.served_kw + z.flex_served_kw for z in self.zones)
        total_unmet = sum(z.unmet_kw + z.flex_unmet_kw for z in self.zones)
        self.peak_served_kw = max(self.peak_served_kw, total_served)

        # 4) kWh accumulation for this tick
        hours = tick_s / 3600.0
        self.total_served_kwh += total_served * hours
        self.total_unmet_kwh += total_unmet * hours
        self.total_flex_served_kwh += sum(z.flex_served_kw for z in self.zones) * hours
        self.total_flex_unmet_kwh += sum(z.flex_unmet_kw for z in self.zones) * hours

        # 5) Log row (for pandas/plots)
        row = {
            "t_s": self.env.now,
            "hour": hour,
            "capacity_kw": self.capacity_kw,
            "total_req_kw": total_req,
            "total_flex_req_kw": total_flex_req,
            "total_served_kw": total_served,
            "total_unmet_kw": total_unmet,
        }
        for z in self.zones:
            row[f"{z.cfg.name}_req_kw"] = z.request_kw
            row[f"{z.cfg.name}_served_kw"] = z.served_kw
            row[f"{z.cfg.name}_unmet_kw"] = z.unmet_kw
            row[f"{z.cfg.name}_flex_req_kw"] = z.flex_request_kw
            row[f"{z.cfg.name}_flex_served_kw"] = z.flex_served_kw
            row[f"{z.cfg.name}_flex_unmet_kw"] = z.flex_unmet_kw

        self.log_rows.append(row)


def energy_process(env: simpy.Environment, mgr: EnergyManager, tick_s: int, start_hour: float):
    while True:
        mgr.allocate(tick_s=tick_s, start_hour=start_hour)
        yield env.timeout(tick_s)


# -----------------------------
# Run
# -----------------------------

def run(
    sim_hours: float = 6.0,
    tick_s: int = 300,               # 5 minutes per energy decision tick
    start_hour: float = 6.0,         # start at 6am to catch morning peak
    capacity_kw: float = 220.0,
    seed: int = 7,
    out_csv: str = r"runs\energy_zones_log.csv"
):
    random.seed(seed)
    env = simpy.Environment()

    # Example zones (edit these to match your report narrative)
    zone_cfgs = [
        EnergyZoneConfig("hospital", base_kw=60, peak_kw=25, priority=1, flexible_kw=5),
        EnergyZoneConfig("residential", base_kw=45, peak_kw=35, priority=2, flexible_kw=18),
        EnergyZoneConfig("commercial", base_kw=35, peak_kw=30, priority=3, flexible_kw=12),
        EnergyZoneConfig("industrial", base_kw=40, peak_kw=20, priority=4, flexible_kw=15),
        EnergyZoneConfig("ev_charging", base_kw=10, peak_kw=5, priority=5, flexible_kw=35),
    ]
    zones = [EnergyZone(env, cfg) for cfg in zone_cfgs]

    log_rows = []
    mgr = EnergyManager(env, zones, capacity_kw=capacity_kw, log_rows=log_rows)

    env.process(energy_process(env, mgr, tick_s=tick_s, start_hour=start_hour))
    env.run(until=sim_hours * 3600)

    df = pd.DataFrame(log_rows)
    df.to_csv(out_csv, index=False)

    print(f"Saved energy log: {out_csv}")
    print(f"Simulated hours: {sim_hours}")
    print(f"Peak requested (kW): {mgr.peak_requested_kw:.2f}")
    print(f"Peak served (kW): {mgr.peak_served_kw:.2f}")
    print(f"Total served (kWh): {mgr.total_served_kwh:.2f}")
    print(f"Total unmet (kWh): {mgr.total_unmet_kwh:.2f}")
    print(f"Flex served (kWh): {mgr.total_flex_served_kwh:.2f}")
    print(f"Flex unmet (kWh): {mgr.total_flex_unmet_kwh:.2f}")


if __name__ == "__main__":
    run()