#!/usr/bin/env bash
# Launch OpenJarvis backend + frontend + open browser
cd "$(dirname "$0")"
set -a; source .env; set +a

# Kill any stale processes on our ports
powershell -Command "
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue }
" 2>/dev/null
sleep 2

echo "Starting Jarvis backend on http://127.0.0.1:8000 ..."
uv run python -u -c "from openjarvis.cli.serve import serve; serve(standalone_mode=False)" &
BACKEND_PID=$!

sleep 5

echo "Starting Jarvis frontend on http://localhost:5173 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

sleep 4
echo ""
echo "========================================"
echo "  Jarvis is running!"
echo "  Backend:  http://127.0.0.1:8000"
echo "  Frontend: http://localhost:5173"
echo "========================================"
start http://localhost:5173 2>/dev/null

echo "Press Ctrl+C to stop."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Jarvis stopped.'" EXIT
wait
