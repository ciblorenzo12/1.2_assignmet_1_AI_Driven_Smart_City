import simpy
import random
import pandas as pd


class FixedTimeController:
    def __init__(self, green_ns=20, green_ew=20):
        self.green_ns = green_ns
        self.green_ew = green_ew

    def next_phase(self, current):
        if current == "NS":
            return "EW", self.green_ew
        return "NS", self.green_ns


class Intersection:
    def __init__(self, env, controller, service_time=2):
        self.env = env
        self.controller = controller

        self.q_ns = simpy.Store(env)
        self.q_ew = simpy.Store(env)

        self.phase = "NS"
        self.phase_ends_at = 0
        self.service_time = service_time

        env.process(self.signal_process())
        env.process(self.release_process())

    def signal_process(self):
        self.phase = "NS"
        self.phase_ends_at = self.env.now + self.controller.green_ns

        while True:
            yield self.env.timeout(max(0, self.phase_ends_at - self.env.now))
            self.phase, dur = self.controller.next_phase(self.phase)
            self.phase_ends_at = self.env.now + dur

    def release_process(self):
        while True:
            active = self.q_ns if self.phase == "NS" else self.q_ew
            if len(active.items) > 0:
                v = yield active.get()
                v["depart_t"] = self.env.now
                v["wait_s"] = v["depart_t"] - v["arrive_t"]
                yield v["done"].succeed()
            yield self.env.timeout(self.service_time)


def vehicle_generator(env, inter: Intersection, approach: str, rate_per_min: float, done_list: list):
    i = 0
    while True:
        dt = random.expovariate(rate_per_min / 60.0)
        yield env.timeout(dt)
        i += 1

        v = {
            "id": f"{approach}-{i}",
            "approach": approach,
            "arrive_t": env.now,
            "depart_t": None,
            "wait_s": None,
            "done": env.event(),
        }

        if approach == "NS":
            yield inter.q_ns.put(v)
        else:
            yield inter.q_ew.put(v)

        # track completion
        env.process(wait_for_done(env, v, done_list))


def wait_for_done(env, v, done_list):
    yield v["done"]
    done_list.append({
        "id": v["id"],
        "approach": v["approach"],
        "arrive_t": v["arrive_t"],
        "depart_t": v["depart_t"],
        "wait_s": v["wait_s"],
    })


def monitor(env, inter: Intersection, snapshots: list, every_s=1):
    while True:
        snapshots.append({
            "t": env.now,
            "q_ns": len(inter.q_ns.items),
            "q_ew": len(inter.q_ew.items),
            "phase": inter.phase,
        })
        yield env.timeout(every_s)


def run(sim_minutes=10, ns_rate=18, ew_rate=12, seed=7, out_csv = r"runs\one_intersection_snapshots.csv"):
    random.seed(seed)
    env = simpy.Environment()

    controller = FixedTimeController(green_ns=20, green_ew=20)
    inter = Intersection(env, controller, service_time=2)

    snapshots = []
    done_list = []

    env.process(vehicle_generator(env, inter, "NS", rate_per_min=ns_rate, done_list=done_list))
    env.process(vehicle_generator(env, inter, "EW", rate_per_min=ew_rate, done_list=done_list))
    env.process(monitor(env, inter, snapshots, every_s=1))

    env.run(until=sim_minutes * 60)

    snap_df = pd.DataFrame(snapshots)
    done_df = pd.DataFrame(done_list)

    snap_df.to_csv(out_csv, index=False)

    avg_wait = float("nan") if done_df.empty else done_df["wait_s"].mean()
    throughput = len(done_df) / sim_minutes  # vehicles per minute

    print(f"Saved snapshots: {out_csv}")
    print(f"Completed vehicles: {len(done_df)}")
    print(f"Avg wait (s): {avg_wait:.2f}")
    print(f"Throughput (veh/min): {throughput:.2f}")


if __name__ == "__main__":
    run()