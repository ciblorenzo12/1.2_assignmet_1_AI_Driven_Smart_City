# AI-Driven Smart City: Traffic + Energy Optimization (Python + Unity Viewer)

This project models a **smart-city system** that controls **traffic lights** across multiple intersections and manages **energy usage** across multiple zones using both **rule-based logic** and **AI models**. The core simulations run in Python (SimPy), produce metrics and CSV logs, and a Unity scene replays those CSVs as an engine deliverable with interactive dropdowns to switch modes.

## What’s Included
- **Traffic simulation (2×2 grid)** with intersections A–D, vehicle flow, queues, and signal phases
- **Traffic controllers**:
  - Fixed-time (rule-based)
  - Actuated (rule-based)
  - **Decision Tree controller** (AI)
- **Energy zone simulation** with base + flexible demand, capacity limits, and unmet demand tracking
- **Energy forecasting model** (predictive) and **forecast-aware allocation mode**
- **Metrics**: average wait time, throughput, demand served/unmet, capacity usage
- **Visual outputs**: plots/heatmaps (energy) and animated GIFs (traffic)
- **Unity engine viewer**: replays traffic + energy CSVs and provides dropdowns to switch modes

---

## Tech Stack
**Python:** SimPy, pandas, numpy, matplotlib, scikit-learn, joblib  
**Unity:** 3D (Core), TextMeshPro UI, CSV replay via StreamingAssets

---

## Project Layout (Python)
Typical structure:
src/
ai_city/
sim_one_intersection.py
sim_grid_2x2.py
animate_one_intersection.py
animate_grid_2x2.py
train_dt_traffic.py
compare_traffic_controllers.py
sim_energy_zones.py
train_energy_forecast.py
plot_energy_results.py
runs/ # generated outputs (CSVs, plots, GIFs)


---

## Setup (Python / Windows PowerShell)

From the project root:

1) Activate your venv:
```powershell
.\.venv\Scripts\Activate.ps1
Ensure imports work (src layout):

$env:PYTHONPATH="$PWD\src"
Install dependencies:

pip install simpy pandas numpy matplotlib scikit-learn joblib pillow
Ensure output folder exists:

New-Item -ItemType Directory -Force -Path .\runs | Out-Null
Generate Traffic Deliverables (Python)
1) Train Decision Tree traffic model
Creates:

runs/dt_training_data.csv

runs/dt_traffic_model.pkl

python -m ai_city.train_dt_traffic
2) Compare controllers (Fixed vs Actuated vs Decision Tree)
Creates:

runs/traffic_controller_comparison.csv

python -m ai_city.compare_traffic_controllers
3) Generate snapshots for animation (DT run)
Creates:

runs/grid_2x2_snapshots.csv

python -c "from ai_city.sim_grid_2x2 import run; run(controller_kind='dt', out_csv=r'runs\grid_2x2_snapshots.csv')"
4) Create the traffic GIF
Creates:

runs/grid_2x2.gif

python -m ai_city.animate_grid_2x2
Optional: Generate 3 traffic snapshot files for Unity dropdown switching
python -c "from ai_city.sim_grid_2x2 import run; run(controller_kind='fixed', out_csv=r'runs\grid_2x2_snapshots_fixed.csv')"
python -c "from ai_city.sim_grid_2x2 import run; run(controller_kind='actuated', out_csv=r'runs\grid_2x2_snapshots_actuated.csv')"
python -c "from ai_city.sim_grid_2x2 import run; run(controller_kind='dt', out_csv=r'runs\grid_2x2_snapshots_dt.csv')"
Generate Energy Deliverables (Python)
1) Baseline energy simulation
Creates:

runs/energy_zones_log.csv

python -m ai_city.sim_energy_zones
2) Plot baseline energy results
Creates PNGs in runs/energy_baseline/

New-Item -ItemType Directory -Force -Path .\runs\energy_baseline | Out-Null
python -c "from ai_city.plot_energy_results import plot; plot(out_dir=r'runs\energy_baseline', csv_path=r'runs\energy_zones_log.csv')"
3) Train energy forecast model
Creates:

runs/energy_forecast_model.pkl

python -m ai_city.train_energy_forecast
4) Forecast-aware (optimized) energy simulation
Creates:

runs/energy_zones_log_forecast.csv

$env:AI_CITY_USE_FORECAST="1"
python -m ai_city.sim_energy_zones
Remove-Item Env:\AI_CITY_USE_FORECAST
5) Plot forecast energy results
Creates PNGs in runs/energy_forecast/

New-Item -ItemType Directory -Force -Path .\runs\energy_forecast | Out-Null
python -c "from ai_city.plot_energy_results import plot; plot(out_dir=r'runs\energy_forecast', csv_path=r'runs\energy_zones_log_forecast.csv')"
Unity Engine Viewer (Deliverable)
What the Unity viewer does
Replays traffic snapshots CSVs as a 2×2 city layout (A–D)

Shows queue bars and signal phase state

Displays an energy UI panel (request/served/unmet + forecast prediction when available)

Dropdowns:

Energy: Baseline vs Forecast

Traffic: Fixed vs Actuated vs Decision Tree

Required Unity files
Copy these CSVs from Python runs/ into:
Assets/StreamingAssets/

Minimum:

grid_2x2_snapshots.csv

energy_zones_log.csv

energy_zones_log_forecast.csv

For traffic dropdown switching:

grid_2x2_snapshots_fixed.csv

grid_2x2_snapshots_actuated.csv

grid_2x2_snapshots_dt.csv

Running the viewer
Open the Unity project in Unity Hub (recommended LTS).

Open the scene (e.g., TrafficEnergyViewer.unity).

Press Play.

Use dropdowns to switch modes.

Deliverables Produced
Traffic:

traffic_controller_comparison.csv

grid_2x2.gif

snapshot CSVs (grid_2x2_snapshots*.csv)

Energy:

baseline + forecast logs (energy_zones_log*.csv)

baseline + forecast plots/heatmaps (PNG)

Unity:

engine replay viewer scene + scripts + StreamingAssets CSVs

Git Notes (Unity)
Commit:

Assets/ (including StreamingAssets/)

Packages/

ProjectSettings/

Ignore:

Library/

Temp/

Obj/

Logs/

IDE files like .vs/, *.sln, *.csproj

Do not ignore *.meta.

Full “Run Everything” Command List
From project root:

.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="$PWD\src"
pip install simpy pandas numpy matplotlib scikit-learn joblib pillow
New-Item -ItemType Directory -Force -Path .\runs | Out-Null

python -m ai_city.train_dt_traffic
python -m ai_city.compare_traffic_controllers
python -c "from ai_city.sim_grid_2x2 import run; run(controller_kind='dt', out_csv=r'runs\grid_2x2_snapshots.csv')"
python -m ai_city.animate_grid_2x2

python -m ai_city.sim_energy_zones
New-Item -ItemType Directory -Force -Path .\runs\energy_baseline | Out-Null
python -c "from ai_city.plot_energy_results import plot; plot(out_dir=r'runs\energy_baseline', csv_path=r'runs\energy_zones_log.csv')"

python -m ai_city.train_energy_forecast
$env:AI_CITY_USE_FORECAST="1"
python -m ai_city.sim_energy_zones
Remove-Item Env:\AI_CITY_USE_FORECAST

New-Item -ItemType Directory -Force -Path .\runs\energy_forecast | Out-Null
python -c "from ai_city.plot_energy_results import plot; plot(out_dir=r'runs\energy_forecast', csv_path=r'runs


::contentReference[oaicite:0]{index=0}