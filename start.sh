#!/usr/bin/env bash
# start.sh — Launch all 5 MarketVentures services (Linux/Mac/WSL)
# Usage: ./start.sh [--force]  (--force kills any existing process on each port)

FORCE=0
[[ "$1" == "--force" ]] && FORCE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$ROOT/logs"

declare -A SERVICES=(
    ["price-recon"]="8000"
    ["market-data-hub"]="8001"
    ["alpha-pipeline"]="8501"
    ["data-onboard"]="8003"
    ["market-ops"]="8004"
)

declare -A CMDS=(
    ["price-recon"]="python -m uvicorn api.routes:app --host 0.0.0.0 --port 8000"
    ["market-data-hub"]="python -m uvicorn api.routes:app --host 0.0.0.0 --port 8001"
    ["alpha-pipeline"]="streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"
    ["data-onboard"]="python -m uvicorn api.routes:app --host 0.0.0.0 --port 8003"
    ["market-ops"]="python -m uvicorn api.routes:app --host 0.0.0.0 --port 8004"
)

for svc in price-recon market-data-hub alpha-pipeline data-onboard market-ops; do
    port="${SERVICES[$svc]}"
    existing=$(lsof -ti tcp:"$port" 2>/dev/null)

    if [[ -n "$existing" ]]; then
        if [[ "$FORCE" == "1" ]]; then
            kill -9 $existing 2>/dev/null
            echo "  killed PID $existing on :$port"
            sleep 0.3
        else
            echo "[$svc] port :$port already in use (PID $existing). Use --force to kill and restart."
            continue
        fi
    fi

    cmd="${CMDS[$svc]}"
    log="$ROOT/logs/$svc.log"
    (cd "$ROOT/$svc" && $cmd >"$log" 2>"$log.err" &)
    echo "[$svc] started on :$port  (log: logs/$svc.log)"
done

echo ""
echo "Dashboards:"
echo "  price-recon      http://localhost:8000"
echo "  market-data-hub  http://localhost:8001"
echo "  alpha-pipeline   http://localhost:8501"
echo "  data-onboard     http://localhost:8003"
echo "  market-ops       http://localhost:8004"
