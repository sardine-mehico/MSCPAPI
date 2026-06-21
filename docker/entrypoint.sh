#!/usr/bin/env bash
# Container entrypoint. Two modes, selected by $MODE:
#   server (default) — headless OpenAI-compatible API (uvicorn)
#   login            — one-time interactive Microsoft sign-in over noVNC
set -euo pipefail

cd /app

MODE="${MODE:-server}"

if [ "$MODE" = "login" ]; then
    echo "[entrypoint] LOGIN mode — starting virtual display + noVNC"
    export DISPLAY=":99"
    NOVNC_PORT="${NOVNC_PORT:-6080}"

    # Virtual X display for the visible browser.
    Xvfb :99 -screen 0 1440x900x24 -ac +extension RANDR >/tmp/xvfb.log 2>&1 &
    # Wait for the X socket before launching anything that needs the display.
    for _ in $(seq 1 50); do
        [ -S /tmp/.X11-unix/X99 ] && break
        sleep 0.1
    done

    fluxbox >/tmp/fluxbox.log 2>&1 &
    # VNC server bound to loopback only (reach it via the noVNC bridge / SSH tunnel).
    x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet \
        >/tmp/x11vnc.log 2>&1 &
    # noVNC web client -> VNC. Binds 0.0.0.0 inside the container; the compose
    # file maps it to 127.0.0.1 on the host.
    websockify --web /usr/share/novnc "${NOVNC_PORT}" localhost:5900 \
        >/tmp/novnc.log 2>&1 &

    echo "[entrypoint] noVNC ready -> http://localhost:${NOVNC_PORT}/vnc.html"
    exec python -m copilot.login_service
fi

echo "[entrypoint] SERVER mode — starting uvicorn"
# Never pop a GUI from the headless server; a missing session must error cleanly.
export COPILOT_AUTO_LOGIN="${COPILOT_AUTO_LOGIN:-0}"
exec uvicorn server.api:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --workers 1 \
    --limit-concurrency "${MAX_CONCURRENCY:-3}"
