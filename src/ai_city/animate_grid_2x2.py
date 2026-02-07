import pandas as pd

# Backend safety (you hit a Tk blit crash earlier).
# Prefer QtAgg if available; otherwise fallback to Agg (GIF output).
import matplotlib
try:
    matplotlib.use("QtAgg")
    _BACKEND = "QtAgg"
except Exception:
    matplotlib.use("Agg")
    _BACKEND = "Agg"

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


def animate(csv_path=r"runs\grid_2x2_snapshots.csv", save_gif=False):
    df = pd.read_csv(csv_path)

    # Layout coordinates for intersections
    pos = {
        "A": (0, 1),  # top-left
        "B": (1, 1),  # top-right
        "C": (0, 0),  # bottom-left
        "D": (1, 0),  # bottom-right
    }

    fig, ax = plt.subplots()
    ax.set_title("2x2 Grid — Queue Bars + Light Phase (NS vs EW)")
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(-0.6, 1.6)
    ax.set_aspect("equal", adjustable="box")

    # Draw roads (simple lines)
    ax.plot([0, 1], [1, 1])
    ax.plot([0, 1], [0, 0])
    ax.plot([0, 0], [0, 1])
    ax.plot([1, 1], [0, 1])

    # Draw nodes + bars
    # For each intersection, we draw:
    # - NS bar above node (vertical height)
    # - EW bar right of node (vertical height, but placed to the right)
    bars = {}
    texts = {}

    count_labels = {}

    # Determine a decent max for bar scaling
    q_cols = [c for c in df.columns if c.endswith("_q_ns") or c.endswith("_q_ew")]
    qmax = max(df[q_cols].max().max(), 10)

    for name, (x, y) in pos.items():
        ax.scatter([x], [y], s=250)

        # NS bar near node (slightly left)
        ns_rect = ax.bar([x - 0.12], [0.0], width=0.18)[0]
        # EW bar near node (slightly right)
        ew_rect = ax.bar([x + 0.12], [0.0], width=0.18)[0]

        bars[name] = (ns_rect, ew_rect)
        texts[name] = ax.text(x, y - 0.18, name, ha="center")
        # Numeric queue labels (show exact counts)
        ns_txt = ax.text(x - 0.12, y + 0.12, "NS:0", ha="center", va="bottom", fontsize=8)
        ew_txt = ax.text(x + 0.12, y + 0.12, "EW:0", ha="center", va="bottom", fontsize=8)
        count_labels[name] = (ns_txt, ew_txt)

    info = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top")
 
    legend = ax.text(
        0.02, 0.90,
        "Bars: left=NS queue, right=EW queue\n"
        "Opacity: solid=GREEN, faded=RED",
        transform=ax.transAxes,
        va="top",
        fontsize=9
        )

    def update(i):
        row = df.iloc[i]
        t = int(row["t"])
        info.set_text(f"t={t}s | backend={_BACKEND}")

        for name in pos.keys():
            qns = int(row[f"{name}_q_ns"])
            qew = int(row[f"{name}_q_ew"])
            phase = row[f"{name}_phase"]
            ns_txt, ew_txt = count_labels[name]
            ns_txt.set_text(f"NS:{qns}")
            ew_txt.set_text(f"EW:{qew}")

            ns_rect, ew_rect = bars[name]
            ns_rect.set_height(qns / qmax * 1.0)
            ew_rect.set_height(qew / qmax * 1.0)

            # Alpha indicates which direction is green
            if phase == "NS":
                ns_rect.set_alpha(1.0)
                ew_rect.set_alpha(0.25)
            else:
                ns_rect.set_alpha(0.25)
                ew_rect.set_alpha(1.0)

        return []

    anim = FuncAnimation(fig, update, frames=len(df), interval=50, blit=False)

    # If running without a GUI backend, auto-save a GIF.
    if save_gif or _BACKEND == "Agg":
        out = r"runs\grid_2x2.gif"
        anim.save(out, writer="pillow", fps=20)
        print(f"Saved GIF: {out}")

    if _BACKEND != "Agg":
        plt.show()


if __name__ == "__main__":
    animate(save_gif=True)