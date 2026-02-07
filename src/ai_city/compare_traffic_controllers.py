import os
import shutil
import pandas as pd

from ai_city.sim_grid_2x2 import run


def move_if_exists(src, dst):
    if os.path.exists(src):
        shutil.move(src, dst)


def summarize_done(done_csv, sim_time_s):
    df = pd.read_csv(done_csv)
    completed = len(df)
    avg_wait = float(df["total_wait_s"].mean()) if completed else float("nan")
    throughput_vpm = completed / (sim_time_s / 60.0) if sim_time_s > 0 else float("nan")
    return {
        "completed": completed,
        "avg_total_wait_s": avg_wait,
        "throughput_veh_per_min": throughput_vpm,
    }


if __name__ == "__main__":
    os.makedirs("runs", exist_ok=True)
    results = []

    for kind in ["fixed", "actuated", "dt"]:
        print("\n==============================")
        print(f"Running controller: {kind}")
        print("==============================")

        # 1) run simulation -> snapshots CSV
        out_snap = rf"runs\grid_2x2_{kind}_snapshots.csv"
        run(controller_kind=kind, out_csv=out_snap)

        # 2) compute sim duration from snapshots
        snap_df = pd.read_csv(out_snap)
        sim_time_s = float(snap_df["t"].iloc[-1])

        # 3) sim_grid_2x2 writes these fixed names each run
        done_src = r"runs\grid_2x2_done.csv"
        events_src = r"runs\grid_2x2_events.csv"

        # 4) define destination names (THIS must be before summarize_done)
        done_dst = rf"runs\grid_2x2_done_{kind}.csv"
        events_dst = rf"runs\grid_2x2_events_{kind}.csv"

        # 5) move to preserve per-controller results
        move_if_exists(done_src, done_dst)
        move_if_exists(events_src, events_dst)

        # 6) ensure done file exists before reading
        if not os.path.exists(done_dst):
            raise FileNotFoundError(
                f"Expected {done_dst} but it wasn't created. "
                f"Check sim_grid_2x2.py writes runs/grid_2x2_done.csv"
            )

        # 7) summarize
        s = summarize_done(done_dst, sim_time_s)
        s["controller"] = kind
        results.append(s)

    summary = pd.DataFrame(results)
    summary_path = r"runs\traffic_controller_comparison.csv"
    summary.to_csv(summary_path, index=False)

    print("\n=== Comparison Summary ===")
    print(summary)
    print(f"\nSaved: {summary_path}")