import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


def animate(csv_path=r"runs\one_intersection_snapshots.csv", save_gif=False):
    df = pd.read_csv(csv_path)

    fig, ax = plt.subplots()
    ax.set_title("One Intersection — Queues + Light Phase")
    ax.set_xlim(-1, 6)
    ax.set_ylim(0, max(df["q_ns"].max(), df["q_ew"].max(), 10) + 2)

    # Intersection node (just a dot for now)
    ax.scatter([2.5], [0.5], s=200)

    # Queue bars
    ns_bar = ax.bar([1.5], [0], width=0.8)[0]
    ew_bar = ax.bar([3.5], [0], width=0.8)[0]

    ax.text(1.5, 0.2, "NS", ha="center")
    ax.text(3.5, 0.2, "EW", ha="center")

    phase_txt = ax.text(0.02, 0.95, "", transform=ax.transAxes)

    def update(i):
        row = df.iloc[i]
        qns = int(row["q_ns"])
        qew = int(row["q_ew"])
        phase = row["phase"]
        t = int(row["t"])

        ns_bar.set_height(qns)
        ew_bar.set_height(qew)

        # alpha indicates which direction is green
        if phase == "NS":
            ns_bar.set_alpha(1.0)
            ew_bar.set_alpha(0.3)
        else:
            ns_bar.set_alpha(0.3)
            ew_bar.set_alpha(1.0)

        phase_txt.set_text(f"t={t}s | phase={phase} | q_ns={qns} q_ew={qew}")
        return ns_bar, ew_bar, phase_txt

    anim = FuncAnimation(fig, update, frames=len(df), interval=50, blit=False)

    if save_gif:
        anim.save("runs/one_intersection.gif", writer="pillow", fps=20)
        print("Saved: runs/one_intersection.gif")

    plt.show()


if __name__ == "__main__":
    animate(save_gif=False)