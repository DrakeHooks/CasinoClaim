#!/usr/bin/env bash
set -euo pipefail

# ---- Find a free display :99..:109 ----
pick_display() {
  for d in $(seq 99 109); do
    if [ ! -S "/tmp/.X11-unix/X${d}" ] && [ ! -f "/tmp/.X${d}-lock" ]; then
      echo "${d}"
      return 0
    fi
  done
  # fallback: use :99 and clear locks
  echo "99"
}
DNUM="$(pick_display)"
export DISPLAY=":${DNUM}"

# ---- Clean stale locks for this display ----
rm -f "/tmp/.X${DNUM}-lock" "/tmp/.X11-unix/X${DNUM}" || true
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix || true

# ---- Start Xvfb once ----
Xvfb "${DISPLAY}" -screen 0 1920x1080x24 -ac +extension RANDR +extension RENDER +extension GLX &
XVFB_PID=$!

# ---- Wait for X socket to appear ----
for i in {1..50}; do
  [ -S "/tmp/.X11-unix/X${DNUM}" ] && break
  sleep 0.2
done

# ---- Minimal WM & VNC ----
fluxbox >/dev/null 2>&1 &
x11vnc -nopw -display "${DISPLAY}" -forever -shared -repeat -rfbport 5900 >/dev/null 2>&1 &

# ---- Per-run Chrome profile (prevents "in use") ----
# Root is persisted via volume; subdir is unique per container+pid
CHROME_USER_DATA_DIR="${CHROME_USER_DATA_DIR:-/data/chrome}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-Default}"
HOSTTAG="${HOSTNAME:-ctr}"
RUN_ID="run-$(date +%s)-$$"

export CHROME_INSTANCE_DIR="${CHROME_USER_DATA_DIR}/${HOSTTAG}/${RUN_ID}"
mkdir -p "${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}" || true
find "${CHROME_INSTANCE_DIR}" -maxdepth 2 -type f -name 'Singleton*' -delete || true

# ---- Run your app ----
exec /venv/bin/python /app/main.py
