import os
import pandas as pd
import joblib

from sklearn.tree import DecisionTreeClassifier

import simpy
import random


import ai_city.sim_grid_2x2 as grid


class DataCollectorController:
    """
    Wraps a base controller (teacher) and logs features + chosen action
    to build a supervised learning dataset.
    """
    def __init__(self, teacher_controller, rows):
        self.teacher = teacher_controller
        self.rows = rows

    def decide(self, inter, now):
        # teacher decision
        action, dt = self.teacher.decide(inter, now)

        # features from intersection state
        qns, qew = inter.queues()
        time_in_phase = now - inter.phase_start
        phase_is_ns = 1 if inter.phase == "NS" else 0

        self.rows.append({
            "q_ns": qns,
            "q_ew": qew,
            "phase_is_ns": phase_is_ns,
            "time_in_phase": time_in_phase,
            "red_wait_ns": inter.red_wait_ns,
            "red_wait_ew": inter.red_wait_ew,
            "label_switch": 1 if action == "SWITCH" else 0,
        })

        return action, dt


def collect_training_data(
    sim_minutes=40,
    seed=7,
    west_to_east_rate=18,
    north_to_south_rate=14
):
    random.seed(seed)
    env = simpy.Environment()

 
    teacher = grid.ActuatedController(min_green=8, max_green=40, bias_threshold=4, force_switch_wait=60)
    rows = []
    collector = DataCollectorController(teacher, rows)


    log_events = []
    A = grid.Intersection(env, "A", collector, log_events)
    B = grid.Intersection(env, "B", collector, log_events)
    C = grid.Intersection(env, "C", collector, log_events)
    D = grid.Intersection(env, "D", collector, log_events)
    intersections = [A, B, C, D]

    done = []
    snapshots = []

    # Routes (same as your sim_grid_2x2)
    def entry_w2e_top():
        return [(A, "EW"), (B, "EW")]

    def entry_w2e_bottom():
        return [(C, "EW"), (D, "EW")]

    def entry_n2s_left():
        return [(A, "NS"), (C, "NS")]

    def entry_n2s_right():
        return [(B, "NS"), (D, "NS")]

    env.process(grid.poisson_generator(env, entry_w2e_top,    west_to_east_rate * 0.5, "W2E_T", done))
    env.process(grid.poisson_generator(env, entry_w2e_bottom, west_to_east_rate * 0.5, "W2E_B", done))
    env.process(grid.poisson_generator(env, entry_n2s_left,   north_to_south_rate * 0.5, "N2S_L", done))
    env.process(grid.poisson_generator(env, entry_n2s_right,  north_to_south_rate * 0.5, "N2S_R", done))

    env.process(grid.monitor(env, intersections, snapshots, every_s=1))
    env.run(until=sim_minutes * 60)

    return pd.DataFrame(rows)


def train_and_save(df, model_path=r"runs\dt_traffic_model.pkl", data_path=r"runs\dt_training_data.csv"):
    os.makedirs("runs", exist_ok=True)

    # Save dataset for report transparency
    df.to_csv(data_path, index=False)
    print(f"Saved training data: {data_path}  (rows={len(df)})")

    X = df[["q_ns", "q_ew", "phase_is_ns", "time_in_phase", "red_wait_ns", "red_wait_ew"]]
    y = df["label_switch"]

    # A small tree is easier to justify + less overfit
    clf = DecisionTreeClassifier(max_depth=5, min_samples_leaf=50, random_state=7)
    clf.fit(X, y)

    joblib.dump(clf, model_path)
    print(f"Saved decision tree model: {model_path}")


if __name__ == "__main__":
    df = collect_training_data(sim_minutes=40, seed=7)
    train_and_save(df)