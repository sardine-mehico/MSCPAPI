# Playwright's official Python image: bundles Chromium + all system deps. The
# tag version MUST match the pinned `playwright` in requirements.txt or the
# bundled browser won't be found. Bump both together.
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

# VNC stack — used ONLY by `login` mode (interactive sign-in over noVNC). Server
# mode runs headless and touches none of these.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
# typing_extensions ships apt-managed in the base image (no pip RECORD), so pip
# can't upgrade it for pydantic/fastapi ("Cannot uninstall ... no RECORD file").
# Install a fresh pip-managed copy first so the requirements install is clean.
RUN pip install --no-cache-dir --ignore-installed typing_extensions \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    MODE=server \
    COPILOT_AUTO_LOGIN=0

# 8000 = OpenAI-compatible API (server mode); 6080 = noVNC (login mode).
EXPOSE 8000 6080

ENTRYPOINT ["/app/docker/entrypoint.sh"]
