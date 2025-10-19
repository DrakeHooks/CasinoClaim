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

# =====================================================================
#            MAIN CHANGE: make Chrome profile persistent
# =====================================================================
CHROME_USER_DATA_DIR="${CHROME_USER_DATA_DIR:-/data/chrome}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-Default}"
USE_EPHEMERAL_PROFILE="${USE_EPHEMERAL_PROFILE:-false}"   # set true to get per-run dirs

HOSTTAG="${HOSTNAME:-ctr}"
RUN_ID="run-$(date +%s)-$$"

if [ "${USE_EPHEMERAL_PROFILE}" = "true" ]; then
  # Old behavior: per-run subdir (NOT persistent)
  export CHROME_INSTANCE_DIR="${CHROME_USER_DATA_DIR}/${HOSTTAG}/${RUN_ID}"
else
  # Persistent: fixed root (reused every container restart)
  export CHROME_INSTANCE_DIR="${CHROME_USER_DATA_DIR}"
fi

# Ensure dirs exist and clear only Chrome lockfiles
mkdir -p "${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}" || true
# If your volume has stricter ownership, ensure it’s writable:
chown -R "$(id -u)":"$(id -g)" "${CHROME_INSTANCE_DIR}" || true
find "${CHROME_INSTANCE_DIR}" -maxdepth 2 -type f -name 'Singleton*' -delete || true

# Optional: FortuneCoins SB/UC can stay ephemeral; no changes needed.
# If someday you want persistent SB profile, set FC_USER_DATA_DIR in compose
# and ensure it exists here (does not affect anything if unset):
if [ -n "${FC_USER_DATA_DIR:-}" ]; then
  mkdir -p "${FC_USER_DATA_DIR}"
  chown -R "$(id -u)":"$(id -g)" "${FC_USER_DATA_DIR}" || true
  find "${FC_USER_DATA_DIR}" -maxdepth 1 -type f -name 'Singleton*' -delete || true
fi
# =====================================================================

# ---- Run your app ----
exec /venv/bin/python /app/main.py
