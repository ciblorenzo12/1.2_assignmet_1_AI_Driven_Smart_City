import os
import math
import pandas as pd
import joblib
from sklearn.tree import DecisionTreeRegressor


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour_sin"] = df["hour"].apply(lambda h: math.sin(2 * math.pi * float(h) / 24.0))
    df["hour_cos"] = df["hour"].apply(lambda h: math.cos(2 * math.pi * float(h) / 24.0))
    return df


def infer_zone_names(df: pd.DataFrame) -> list[str]:
    # Only BASE demand columns: <zone>_req_kw (exclude flex columns)
    zones = sorted({
        c.replace("_req_kw", "")
        for c in df.columns
        if c.endswith("_req_kw")
        and not c.startswith("total_")
        and "_flex_" not in c  # <-- key: don't treat flex columns as zones
    })
    return zones


def train(csv_path=r"runs\energy_zones_log.csv", model_path=r"runs\energy_forecast_model.pkl"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing {csv_path}. Run: python -m ai_city.sim_energy_zones")

    df = pd.read_csv(csv_path)
    if len(df) < 3:
        raise ValueError(f"{csv_path} has too few rows ({len(df)}). Re-run energy sim for longer.")

    # Must have these columns
    required_cols = {"hour", "total_req_kw"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing)}")

    df = add_time_features(df)

    zones = infer_zone_names(df)
    if not zones:
        raise ValueError(
            "Could not infer any zones. Expected columns like 'hospital_req_kw'. "
            f"Columns found: {df.columns.tolist()}"
        )

    feature_cols = ["hour", "hour_sin", "hour_cos", "total_req_kw"] + [f"{z}_req_kw" for z in zones]

    # Create target: next tick total base demand
    df["target_next_total_req_kw"] = df["total_req_kw"].shift(-1)

    # Convert features to numeric, fill NaNs (never drop everything)
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # Only drop rows where target is NaN (last row)
    y = pd.to_numeric(df["target_next_total_req_kw"], errors="coerce")
    keep = y.notna()
    X = X[keep]
    y = y[keep]

    if len(X) == 0:
        # Extra debug info to help immediately
        nan_counts = df[feature_cols + ["target_next_total_req_kw"]].isna().sum().sort_values(ascending=False)
        raise ValueError(
            "No training rows after filtering target NaNs.\n"
            f"CSV rows: {len(df)}\n"
            f"NaN counts (top 10):\n{nan_counts.head(10)}"
        )

    model = DecisionTreeRegressor(max_depth=5, min_samples_leaf=10, random_state=7)
    model.fit(X, y)

    os.makedirs("runs", exist_ok=True)
    joblib.dump({"model": model, "features": feature_cols, "zones": zones}, model_path)

    print(f"Saved energy forecast model: {model_path}")
    print(f"Training rows: {len(X)}")
    print(f"Zones: {zones}")
    print(f"Features: {feature_cols}")


if __name__ == "__main__":
    train()