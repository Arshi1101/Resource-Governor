# Resource Governor

Resource Governor monitors process CPU and memory use, learns per-program baselines, and lowers the priority of sustained CPU outliers. It records samples and actions in SQLite so the Streamlit dashboard can show current queues, process history, and governor overhead.

## Requirements

- Python 3.10 or newer
- Windows or macOS

## Setup

From the project root, create and activate a virtual environment, then install the project dependencies.

### macOS

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

Start the governor in a terminal. Begin in dry-run mode to record detections without changing process priorities:

```sh
python -m governor.main --dry-run
```

In a second terminal, from the project root, start the combined dashboard:

```sh
streamlit run dashboard/app.py
```

The dashboard simulator works without the governor. Live telemetry appears after the governor starts writing data. To enable priority changes, stop the dry-run process and run `python -m governor.main`. Managing processes owned by other users may require elevated permissions on macOS or Windows.

The primary dashboard is `dashboard/app.py`. `dashboard/live.py` can also be run as a standalone live-data view with `streamlit run dashboard/live.py`.

## Configuration and data

- `policy.json` sets default or per-program classes, priority limits, thresholds, and protected programs.
- `data/governor.db` stores samples, governor overhead, and events.
- `data/baselines.json` stores learned baselines.

The governor creates the `data` directory and database as needed. Edit `policy.json` while the governor runs; policy changes are reloaded automatically.

## Utilities

Run these from the project root while the governor is collecting data:

```sh
python tools/report.py 60
python tools/queue_history.py
python tools/incidents.py 60
```

`tools/incidents.py` writes `data/incident_report.md`. `tools/spike.py` generates a configurable CPU or memory workload. `tools/benchmark.py` launches a victim process and one spike process per logical CPU for roughly three minutes; run it only when you intend to stress the machine, with the governor in real (not dry-run) mode.

## Governor options

```sh
python -m governor.main --help
```

Available options include `--dry-run`, `--mode adaptive|static`, `--interval SECONDS`, and `--no-foreground`.
