"""
launch_all.py — Start all 5 MarketVentures services.

Uses the shared .venv at C:/Users/ewanj/MarketVentures/.venv

Services:
  price-recon     → http://localhost:8000
  market-data-hub → http://localhost:8001  (seeds DB on first run)
  alpha-pipeline  → http://localhost:8002  (Streamlit)
  data-onboard    → http://localhost:8003
  market-ops      → http://localhost:8004  (WebSocket dashboard)

Run: python launch_all.py
Stop: Ctrl+C (kills all child processes)
"""
import subprocess
import sys
import time
import signal
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

if not PYTHON.exists():
    sys.exit(f"ERROR: {PYTHON} not found. Run: python -m venv .venv && .venv/Scripts/pip install -r requirements-all.txt")

SERVICES = [
    {"name": "price-recon",     "dir": ROOT / "price-recon",     "port": 8000,
     "cmd": [str(PYTHON), "main.py", "--serve"]},
    {"name": "market-data-hub", "dir": ROOT / "market-data-hub", "port": 8001,
     "cmd": [str(PYTHON), "main.py"]},
    {"name": "alpha-pipeline",  "dir": ROOT / "alpha-pipeline",  "port": 8002,
     "cmd": [str(PYTHON), "main.py", "--serve"]},
    {"name": "data-onboard",    "dir": ROOT / "data-onboard",    "port": 8003,
     "cmd": [str(PYTHON), "main.py"]},
    {"name": "market-ops",      "dir": ROOT / "market-ops",      "port": 8004,
     "cmd": [str(PYTHON), "main.py"]},
]

procs = []

def launch():
    for svc in SERVICES:
        log_path = ROOT / f"logs/{svc['name']}.log"
        log_path.parent.mkdir(exist_ok=True)
        log = open(log_path, "w")
        p = subprocess.Popen(
            svc["cmd"],
            cwd=str(svc["dir"]),
            stdout=log,
            stderr=log,
        )
        procs.append((svc["name"], svc["port"], p, log))
        print(f"  started {svc['name']:20s} PID={p.pid:6d}  → http://localhost:{svc['port']}")
        time.sleep(0.5)  # stagger startup to avoid DB contention

def wait_for_health():
    import urllib.request
    print("\nWaiting for services to come up...")
    for name, port, proc, _ in procs:
        if "alpha-pipeline" in name:
            url = f"http://localhost:{port}/_stcore/health"
        else:
            url = f"http://localhost:{port}/health"
        for attempt in range(20):
            time.sleep(1)
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        print(f"  ✓ {name:20s}  http://localhost:{port}")
                        break
            except Exception:
                pass
        else:
            print(f"  ✗ {name:20s}  not responding after 20s (check logs/{name}.log)")

def open_browsers():
    urls = [
        ("price-recon",     "http://localhost:8000"),
        ("market-data-hub", "http://localhost:8001"),
        ("alpha-pipeline",  "http://localhost:8002"),
        ("data-onboard",    "http://localhost:8003"),
        ("market-ops",      "http://localhost:8004"),
    ]
    print("\nOpening browser tabs...")
    for name, url in urls:
        webbrowser.open_new_tab(url)
        print(f"  opened {name:20s}  {url}")
        time.sleep(0.3)

def shutdown(sig=None, frame=None):
    print("\nShutting down all services...")
    for name, port, p, log in procs:
        p.terminate()
        log.close()
        print(f"  stopped {name}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("MarketVentures — launching all 5 services\n")
    launch()
    wait_for_health()
    open_browsers()

    print("\n─────────────────────────────────────────────")
    print("All services running. Dashboard URLs:")
    print("  price-recon     →  http://localhost:8000")
    print("  market-data-hub →  http://localhost:8001")
    print("  alpha-pipeline  →  http://localhost:8002  (Streamlit)")
    print("  data-onboard    →  http://localhost:8003")
    print("  market-ops      →  http://localhost:8004  (WebSocket dashboard)")
    print("\nPress Ctrl+C to stop all services.")
    print("Launch logs : MarketVentures/logs/<service>.log")
    print("Error logs  : MarketVentures/<service>/logs/error.log")
    print("App logs    : MarketVentures/<service>/logs/app.log")
    print("─────────────────────────────────────────────\n")

    # Keep alive, watch for crashed processes
    while True:
        time.sleep(5)
        for name, port, p, log in procs:
            if p.poll() is not None:
                print(f"  WARNING: {name} exited with code {p.returncode} — check logs/{name}.log")
