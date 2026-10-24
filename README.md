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

## Detailed project abstract

Resource Governor is a local process-monitoring and CPU-priority management tool for Windows and macOS. It samples running processes, builds per-program CPU and memory baselines, and looks for sustained deviations. When a process has an unusually high CPU load for long enough, the governor can lower its operating-system priority in steps. It does not terminate processes. Memory anomalies are recorded and reported because lowering CPU priority does not reclaim memory.

The project has two main parts. The Python governor runs in the background and owns monitoring, policy decisions, priority changes, and persistence. The Streamlit dashboard reads the local SQLite database and presents a simulator, live queue state, recent actions, resource charts, and governor overhead. The primary dashboard is `dashboard/app.py`; it serves the embedded component in `dashboard/component/`. `dashboard/live.py` is an optional standalone Streamlit view of telemetry and feedback controls.

In adaptive mode, CPU and memory observations warm up per-program baselines before anomaly scoring begins. The detector uses an exponentially weighted baseline and configurable floors and thresholds. A CPU anomaly must remain sustained before it can trigger a priority change. The foreground application is protected by default, per-program policy can exclude or classify programs, and permission failures are recorded instead of being treated as successful changes. The governor verifies a change after a delay and can promote a process after sustained calm or age it back toward its base priority. Optional family-level detection can demote a few high-CPU processes when several processes with the same program key are collectively using substantial CPU.

The operating system still decides how CPU time is distributed. Resource Governor changes a process priority as a cooperative signal; it is not a replacement for the operating system scheduler and does not promise a fixed share of CPU. Q0, Q1, and Q2 represent priority levels mapped from the current OS priority. A process can already start at a reduced OS priority, so appearing in Q1 or Q2 does not by itself prove the governor demoted it. Use the intervention log and event history to distinguish governor actions from the process's starting priority.

## File structure

```text
resource-governor/
├── README.md
├── requirements.txt
├── policy.json
├── dashboard/
│   ├── app.py
│   ├── live.py
│   └── component/
│       ├── index.html
│       └── page.html
├── governor/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── policy.py
│   ├── detector.py
│   ├── baseline.py
│   ├── actuator.py
│   ├── context.py
│   ├── family.py
│   ├── leak.py
│   ├── suspect.py
│   ├── feedback.py
│   ├── notify.py
│   └── store.py
├── tools/
│   ├── report.py
│   ├── queue_history.py
│   ├── incidents.py
│   ├── spike.py
│   ├── victim.py
│   └── benchmark.py
└── data/                 # created at runtime; local state and generated reports
    ├── governor.db
    ├── baselines.json
    ├── learned.json
    ├── incident_report.md
    ├── spike_marker.txt
    └── victim_log.csv
```

### Main files

| File | Responsibility |
| --- | --- |
| `governor/main.py` | Main monitoring loop. Enumerates processes, normalizes program keys, evaluates policies and anomalies, coordinates queue changes, writes samples and events, and sends notifications. |
| `governor/config.py` | Runtime defaults and thresholds, protected process names, platform queue classes, paths, and feature switches. |
| `governor/policy.py` | Loads and periodically reloads `policy.json`; returns per-program and default policy values. |
| `governor/detector.py` | Holds per-process runtime state and performs adaptive or static anomaly evaluation. |
| `governor/baseline.py` | Tracks the rolling baseline statistics used by adaptive detection. |
| `governor/actuator.py` | Maps Q0/Q1/Q2 to platform priorities and applies a requested priority to a process. |
| `governor/context.py` | Detects the foreground process and its children for foreground protection. |
| `governor/family.py` | Detects sustained aggregate CPU pressure across related processes and can demote selected members. |
| `governor/leak.py` | Fits memory usage over time and estimates sustained memory growth. |
| `governor/suspect.py` | Scores contextual signals for processes that may warrant review after an intervention. |
| `governor/feedback.py` | Stores operator feedback and adjusts per-program detection strictness. |
| `governor/notify.py` | Sends optional desktop or webhook notifications. |
| `governor/store.py` | Creates and writes the SQLite telemetry, event, and overhead tables. |
| `dashboard/app.py` | Primary Streamlit dashboard. Reads current samples and event history and passes telemetry to the embedded frontend. |
| `dashboard/component/index.html` | Bridges Streamlit component messages to the dashboard page iframe. |
| `dashboard/component/page.html` | Dashboard UI, simulator, interaction logic, and canvas charts. |
| `dashboard/live.py` | Optional standalone Streamlit live telemetry dashboard with interactive feedback controls. |

### Utilities

- `tools/report.py [minutes]` summarizes event counts and governor overhead for a time window (60 minutes by default).
- `tools/queue_history.py` prints recorded priority transitions grouped by process.
- `tools/incidents.py [minutes]` writes an event timeline to `data/incident_report.md`.
- `tools/spike.py` creates a configurable CPU or memory workload for manual observation.
- `tools/victim.py` records a simple throughput workload for benchmarking.
- `tools/benchmark.py` launches a victim and CPU spikes, then compares detected throttling and victim throughput. It deliberately stresses the machine; run it only when you intend to do so.

## Runtime data

The governor creates `data/` as needed. The SQLite database at `data/governor.db` contains:

- `samples`: timestamped process CPU, memory, and anomaly scores.
- `events`: classifications, queue changes, anomaly flags, verification results, and explanatory notes.
- `meta`: governor CPU use, memory use, cycle duration, and process count.
- `feedback`: operator feedback used by the learner.

Adaptive baselines are saved in `data/baselines.json`; learned feedback adjustments are saved in `data/learned.json`. Benchmark and incident utilities can write `data/victim_log.csv`, `data/spike_marker.txt`, and `data/incident_report.md`. The database, baselines, reports, CSV files, and spike marker are excluded from version control by `.gitignore`; `data/learned.json` is also a local runtime file.

## Policy and queue behavior

Program keys are normally lowercased process names. Python scripts and modules receive keys such as `python:spike.py` or `python:package.module`; use the exact key produced by the governor in `policy.json`. Example:

```json
{
  "default": {
    "z_threshold": 3.0
  },
  "programs": {
    "obs": {"never_touch": true},
    "zoom.us": {"class": "interactive"},
    "python:spike.py": {"class": "background", "max_level": 2}
  }
}
```

Available program fields include `never_touch`, `class`, `max_level`, and `z_threshold`. Classes set a starting priority and a maximum demotion level: `interactive`, `normal`, or `background`. The governor reloads policy changes periodically while running. See `governor/config.py` for platform priority mappings and the default protected-process list.

In adaptive mode, the default warm-up is 60 observations. By default, an anomaly must persist for 10 samples; CPU demotions are separated by a cooldown. Static mode uses the fixed CPU and memory thresholds in `governor/config.py`. CPU priority changes do not reduce memory use. On macOS, changing priority for another user's process or restoring a higher priority can require elevated permissions. On Windows, managing processes owned by other users can require Administrator privileges.

The primary dashboard shows all active Q1 processes. Q0 and Q2 share a 30-process display limit, ranked by CPU; the UI reports displayed and active counts. Its queue timeline uses a shorter, three-minute window and plots up to five active sampled processes, including a representative from each occupied queue. Recorded queue transitions are used when available. Processes that have not produced a sample in the current live window may not appear in the “right now” list.

## Troubleshooting

- **No live telemetry:** Confirm the governor is running from the project root and that it is writing `data/governor.db`. The dashboard simulator can run without telemetry.
- **No queue transitions:** In adaptive mode, a process must exceed its learned baseline and remain anomalous for the sustain period. Foreground protection, `never_touch`, cooldowns, and process permissions can prevent a demotion.
- **Dry-run does not change OS priority:** `--dry-run` records proposed actions but intentionally does not call the OS priority setter. Stop it and start the governor without that flag to apply changes.
- **A process appears in Q1 or Q2 without a demotion event:** Queue panels reflect the process's current OS priority. It may have started at that priority or been changed by another application; inspect `Queue movements` or run `python tools/queue_history.py` to see governor-recorded transitions.
- **Permission denied:** The governor records failed actions. Use the appropriate account privileges if you need to manage a process owned by another user.
- **No anomaly during a test:** Confirm the benchmark or spike is running after the governor starts. Adaptive mode needs a baseline warm-up; use static mode or a longer run for controlled experiments, and review the configured floors and thresholds.
