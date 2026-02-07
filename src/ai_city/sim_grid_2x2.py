import simpy
import random
import pandas as pd
import joblib
from dataclasses import dataclass


# -----------------------------
# Controllers
# -----------------------------

@dataclass
class FixedTimeController:
    green_ns: int = 20
    green_ew: int = 20

    def decide(self, inter, now):
        # Hold current phase until its timer ends; switch then.
        time_in = now - inter.phase_start
        if inter.phase == "NS" and time_in >= self.green_ns:
            return "SWITCH", 0
        if inter.phase == "EW" and time_in >= self.green_ew:
            return "SWITCH", 0
        return "HOLD", 1  # re-check every second


@dataclass
class ActuatedController:
    min_green: int = 8
    max_green: int = 40
    bias_threshold: int = 4     # how much bigger opposite queue must be
    force_switch_wait: int = 60 # safety fairness: don't starve a direction forever

    def decide(self, inter, now):
        qns, qew = inter.queues()
        time_in = now - inter.phase_start

        # If we've been green too long, force switch
        if time_in >= self.max_green:
            return "SWITCH", 0

        # Enforce minimum green
        if time_in < self.min_green:
            return "HOLD", 1

        # Fairness: if red direction has been waiting too long, switch
        if inter.phase == "NS" and inter.red_wait_ew >= self.force_switch_wait and qew > 0:
            return "SWITCH", 0
        if inter.phase == "EW" and inter.red_wait_ns >= self.force_switch_wait and qns > 0:
            return "SWITCH", 0

        # Pressure rule: switch if opposite queue is significantly larger
        if inter.phase == "NS":
            if qew > qns + self.bias_threshold:
                return "SWITCH", 0
        else:
            if qns > qew + self.bias_threshold:
                return "SWITCH", 0

        return "HOLD", 1



@dataclass
class DecisionTreeTrafficController:
    model_path: str = r"runs\dt_traffic_model.pkl"
    min_green: int = 8
    max_green: int = 40

    def __post_init__(self):
        self.model = joblib.load(self.model_path)

    def decide(self, inter, now):
        qns, qew = inter.queues()
        time_in = now - inter.phase_start
        phase_is_ns = 1 if inter.phase == "NS" else 0

        # Safety constraints (prevents rapid flip-flopping)
        if time_in < self.min_green:
            return "HOLD", 1
        if time_in >= self.max_green:
            return "SWITCH", 0

        X = [[qns, qew, phase_is_ns, time_in, inter.red_wait_ns, inter.red_wait_ew]]
        pred_switch = int(self.model.predict(X)[0])

        return ("SWITCH", 0) if pred_switch == 1 else ("HOLD", 1)

# -----------------------------
# Agents
# -----------------------------

class Vehicle:
    def __init__(self, env, vid, route, log_done):
        self.env = env
        self.vid = vid
        self.route = route              # list[(Intersection, approach_str)]
        self.log_done = log_done

        self.total_wait = 0.0
        self.last_queue_enter = None
        self.released = None

    def join_queue(self, t):
        self.last_queue_enter = t
        self.released = self.env.event()

    def release(self, t):
        self.total_wait += (t - self.last_queue_enter)
        self.released.succeed()


class Intersection:
    def __init__(self, env, name, controller, log_events, service_time=2):
        self.env = env
        self.name = name
        self.controller = controller
        self.log_events = log_events

        self.q_ns = simpy.Store(env)
        self.q_ew = simpy.Store(env)

        self.phase = "NS"
        self.phase_start = env.now

        # fairness trackers: how long each direction has been red
        self.red_wait_ns = 0
        self.red_wait_ew = 0

        self.service_time = service_time

        env.process(self.signal_process())
        env.process(self.release_process())
        env.process(self.fairness_clock())

    def queues(self):
        return len(self.q_ns.items), len(self.q_ew.items)

    def fairness_clock(self):
        # track red-wait time for each direction
        while True:
            if self.phase == "NS":
                self.red_wait_ew += 1
                self.red_wait_ns = 0
            else:
                self.red_wait_ns += 1
                self.red_wait_ew = 0
            yield self.env.timeout(1)

    def signal_process(self):
        while True:
            action, dt = self.controller.decide(self, self.env.now)

            if action == "SWITCH":
                self.phase = "EW" if self.phase == "NS" else "NS"
                self.phase_start = self.env.now

            qns, qew = self.queues()
            self.log_events.append({
                "t": self.env.now,
                "type": "signal",
                "intersection": self.name,
                "phase": self.phase,
                "q_ns": qns,
                "q_ew": qew,
                "action": action
            })

            yield self.env.timeout(dt)

    def release_process(self):
        while True:
            active_q = self.q_ns if self.phase == "NS" else self.q_ew
            if len(active_q.items) > 0:
                v: Vehicle = yield active_q.get()
                v.release(self.env.now)

                self.log_events.append({
                    "t": self.env.now,
                    "type": "release",
                    "intersection": self.name,
                    "vehicle": v.vid,
                    "phase": self.phase
                })

            yield self.env.timeout(self.service_time)


# -----------------------------
# Simulation plumbing
# -----------------------------

def vehicle_process(env, v: Vehicle, log_done):
    # traverse route intersection by intersection
    for inter, approach in v.route:
        # travel time between intersections
        yield env.timeout(random.uniform(6, 14))

        v.join_queue(env.now)
        if approach == "NS":
            yield inter.q_ns.put(v)
        else:
            yield inter.q_ew.put(v)

        # wait for green release
        yield v.released

    log_done.append({
        "vehicle": v.vid,
        "finish_t": env.now,
        "total_wait_s": v.total_wait
    })


def poisson_generator(env, entry_fn, rate_per_min, prefix, log_done):
    i = 0
    while True:
        dt = random.expovariate(rate_per_min / 60.0)
        yield env.timeout(dt)
        i += 1
        route = entry_fn()
        v = Vehicle(env, f"{prefix}-{i}", route, log_done)
        env.process(vehicle_process(env, v, log_done))


def monitor(env, intersections, snapshots, every_s=1):
    while True:
        row = {"t": env.now}
        for inter in intersections:
            qns, qew = inter.queues()
            row[f"{inter.name}_q_ns"] = qns
            row[f"{inter.name}_q_ew"] = qew
            row[f"{inter.name}_phase"] = inter.phase
        snapshots.append(row)
        yield env.timeout(every_s)


def build_grid_2x2(env, controller_kind="actuated"):
    # coordinates (for your mental model)
    # A = (0,0)  B = (1,0)
    # C = (0,1)  D = (1,1)
    if controller_kind == "fixed":
        controller = FixedTimeController(green_ns=20, green_ew=20)

    elif controller_kind == "dt":
        controller = DecisionTreeTrafficController(
        model_path=r"runs\dt_traffic_model.pkl",
        min_green=8,
        max_green=40
    )

    else:
        controller = ActuatedController(min_green=8, max_green=40, bias_threshold=4, force_switch_wait=60)

    log_events = []
    A = Intersection(env, "A", controller, log_events)
    B = Intersection(env, "B", controller, log_events)
    C = Intersection(env, "C", controller, log_events)
    D = Intersection(env, "D", controller, log_events)
    return [A, B, C, D], log_events


def run(
    sim_minutes=12,
    seed=7,
    controller_kind="actuated",
    west_to_east_rate=18,   # vehicles/min entering left side heading east
    north_to_south_rate=14, # vehicles/min entering top heading south
    out_csv=r"runs\grid_2x2_snapshots.csv"
):
    random.seed(seed)
    env = simpy.Environment()

    intersections, log_events = build_grid_2x2(env, controller_kind=controller_kind)
    # Unpack for easy routing
    A = next(i for i in intersections if i.name == "A")
    B = next(i for i in intersections if i.name == "B")
    C = next(i for i in intersections if i.name == "C")
    D = next(i for i in intersections if i.name == "D")

    done = []
    snapshots = []

    # Routes:
    # West->East on top row: A -> B (approach EW at each)
    def entry_w2e_top():
        return [(A, "EW"), (B, "EW")]

    # West->East on bottom row: C -> D
    def entry_w2e_bottom():
        return [(C, "EW"), (D, "EW")]

    # North->South on left col: A -> C (approach NS at each)
    def entry_n2s_left():
        return [(A, "NS"), (C, "NS")]

    # North->South on right col: B -> D
    def entry_n2s_right():
        return [(B, "NS"), (D, "NS")]

    # Split arrivals across two entry points each
    env.process(poisson_generator(env, entry_w2e_top,    west_to_east_rate * 0.5, "W2E_T", done))
    env.process(poisson_generator(env, entry_w2e_bottom, west_to_east_rate * 0.5, "W2E_B", done))
    env.process(poisson_generator(env, entry_n2s_left,   north_to_south_rate * 0.5, "N2S_L", done))
    env.process(poisson_generator(env, entry_n2s_right,  north_to_south_rate * 0.5, "N2S_R", done))

    env.process(monitor(env, intersections, snapshots, every_s=1))

    env.run(until=sim_minutes * 60)

    snap_df = pd.DataFrame(snapshots)
    done_df = pd.DataFrame(done)
    events_df = pd.DataFrame(log_events)

    snap_df.to_csv(out_csv, index=False)

    avg_wait = float("nan") if done_df.empty else done_df["total_wait_s"].mean()
    throughput_per_min = len(done_df) / sim_minutes

    print(f"Controller: {controller_kind}")
    print(f"Saved snapshots: {out_csv}")
    print(f"Completed vehicles: {len(done_df)}")
    print(f"Avg total wait (s): {avg_wait:.2f}")
    print(f"Throughput (veh/min): {throughput_per_min:.2f}")

    #  save done/events for later analysis
    done_path = r"runs\grid_2x2_done.csv"
    events_path = r"runs\grid_2x2_events.csv"
    done_df.to_csv(done_path, index=False)
    events_df.to_csv(events_path, index=False)
    print(f"Saved: {done_path}")
    print(f"Saved: {events_path}")


if __name__ == "__main__":
    run()