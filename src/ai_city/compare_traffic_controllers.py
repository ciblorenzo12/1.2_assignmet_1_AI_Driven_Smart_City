import os
import shutil
import pandas as pd

from ai_city.sim_grid_2x2 import run


def move_if_exists(src, dst):
    if os.path.exists(src):
        shutil.move(src, dst)


def summarize_done(done_csv):
    df = pd.read_csv(done_csv)
    return {
        "completed": len(df),
        "avg_total_wait_s": float(df["total_wait_s"].mean()) if len(df) else float("nan"),
    }


if __name__ == "__main__":
    os.makedirs("runs", exist_ok=True)

    results = []

    for kind in ["fixed", "actuated", "dt"]:
        print("\n==============================")
        print(f"Running controller: {kind}")
        print("==============================")

        out_snap = rf"runs\grid_2x2_{kind}_snapshots.csv"
        run(controller_kind=kind, out_csv=out_snap)

        # sim_grid_2x2 writes these fixed names; rename to preserve
        done_src = r"runs\grid_2x2_done.csv"
        events_src = r"runs\grid_2x2_events.csv"
        done_dst = rf"runs\grid_2x2_done_{kind}.csv"
        events_dst = rf"runs\grid_2x2_events_{kind}.csv"

        move_if_exists(done_src, done_dst)
        move_if_exists(events_src, events_dst)

        s = summarize_done(done_dst)
        s["controller"] = kind
        results.append(s)

    summary = pd.DataFrame(results)
    summary_path = r"runs\traffic_controller_comparison.csv"
    summary.to_csv(summary_path, index=False)

    print("\n=== Comparison Summary ===")
    print(summary)
    print(f"\nSaved: {summary_path}")