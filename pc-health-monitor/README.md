# PC Health & Performance Monitor

Samples CPU, memory, disk, and uptime on the current machine, stores a short local history, and flags thresholds. Linux/macOS/Windows metrics use `psutil` when installed; standard-library fallbacks still report platform and uptime where available.

```sh
python -m pip install psutil
python monitor.py --samples 3 --interval 2
python monitor.py --history
```

Set `PC_HEALTH_DB` for the SQLite history file. Collection runs locally and does not send telemetry. Hardware counters and available metrics vary by operating system; this is not a remote fleet agent.
