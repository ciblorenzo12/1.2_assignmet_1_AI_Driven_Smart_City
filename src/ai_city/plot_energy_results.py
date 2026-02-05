import pandas as pd

import matplotlib
matplotlib.use("Agg")  # safe backend: saves files, no GUI

import matplotlib.pyplot as plt


def plot(out_dir=r"runs", csv_path=r"runs\energy_zones_log.csv"):
    df = pd.read_csv(csv_path)

    # ---- Plot 1: Total requested vs served vs unmet
    fig = plt.figure()
    plt.plot(df["hour"], df["total_req_kw"] + df["total_flex_req_kw"])
    plt.plot(df["hour"], df["total_served_kw"])
    plt.plot(df["hour"], df["total_unmet_kw"])
    plt.xlabel("Hour of day")
    plt.ylabel("kW")
    plt.title("Energy: Requested vs Served vs Unmet (kW)")
    plt.legend(["requested_total", "served_total", "unmet_total"])
    p1 = rf"{out_dir}\energy_totals.png"
    plt.savefig(p1, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {p1}")

    # ---- Plot 2: Capacity line vs served
    fig = plt.figure()
    plt.plot(df["hour"], df["capacity_kw"])
    plt.plot(df["hour"], df["total_served_kw"])
    plt.xlabel("Hour of day")
    plt.ylabel("kW")
    plt.title("Energy: Capacity vs Served (kW)")
    plt.legend(["capacity", "served_total"])
    p2 = rf"{out_dir}\energy_capacity.png"
    plt.savefig(p2, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {p2}")

    # ---- Heatmap: per-zone unmet base demand (req - served)
    # Collect zone names by parsing columns
        # ---- Heatmap: per-zone unmet base demand (req - served)
    # Only include real zones (exclude totals like total_req_kw / total_flex_req_kw)
    zone_names = sorted({
        c.replace("_unmet_kw", "")
        for c in df.columns
        if c.endswith("_unmet_kw") and not c.startswith("total_")
    })

    unmet_matrix = [df[f"{z}_unmet_kw"].to_list() for z in zone_names]
    for z in zone_names:
        unmet_matrix.append(df[f"{z}_unmet_kw"].to_list())

    fig = plt.figure()
    plt.imshow(unmet_matrix, aspect="auto")
    plt.yticks(range(len(zone_names)), zone_names)
    plt.xticks([0, len(df)//2, len(df)-1], ["start", "mid", "end"])
    plt.xlabel("Time steps")
    plt.title("Heatmap: Unmet Base Demand (kW) by Zone")
    plt.colorbar()
    p3 = rf"{out_dir}\energy_unmet_heatmap.png"
    plt.savefig(p3, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {p3}")


if __name__ == "__main__":
    plot()
