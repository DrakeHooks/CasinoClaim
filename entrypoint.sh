#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  DISPLAY / Xvfb / VNC setup
# ============================================================
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

# Clean stale locks and sockets
rm -f "/tmp/.X${DNUM}-lock" "/tmp/.X11-unix/X${DNUM}" || true
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix || true

# Start virtual display & wait for it
Xvfb "${DISPLAY}" -screen 0 1920x1080x24 -ac +extension RANDR +extension RENDER +extension GLX &
XVFB_PID=$!
for i in {1..50}; do
  [ -S "/tmp/.X11-unix/X${DNUM}" ] && break
  sleep 0.2
done

# Lightweight window manager + VNC
fluxbox >/dev/null 2>&1 &
x11vnc -nopw -display "${DISPLAY}" -forever -shared -repeat -rfbport 5900 >/dev/null 2>&1 &


# ============================================================
#  PERSISTENT CHROME PROFILE SETUP
# ============================================================

# Root of Chrome user data
CHROME_USER_DATA_DIR="${CHROME_USER_DATA_DIR:-/data/chrome}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-Default}"
USE_EPHEMERAL_PROFILE="${USE_EPHEMERAL_PROFILE:-false}"  # set to true to get per-run dirs

HOSTTAG="${HOSTNAME:-ctr}"
RUN_ID="run-$(date +%s)-$$"

# Decide between persistent or ephemeral profile
if [ "${USE_EPHEMERAL_PROFILE}" = "true" ]; then
  export CHROME_INSTANCE_DIR="${CHROME_USER_DATA_DIR}/${HOSTTAG}/${RUN_ID}"
else
  export CHROME_INSTANCE_DIR="${CHROME_USER_DATA_DIR}"
fi

# Ensure Chrome dirs exist
mkdir -p "${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}" || true

# Fix ownership so Chrome can write to the mounted volume
chown -R "$(id -u)":"$(id -g)" "${CHROME_INSTANCE_DIR}" || true

# Kill any stray Chrome using the same profile (from crashes / restarts)
pkill -9 -f "chrome.*--user-data-dir=${CHROME_INSTANCE_DIR}" || true
pkill -9 -f "chrome" || true

# Remove leftover Chrome locks / sockets
find "${CHROME_INSTANCE_DIR}" -maxdepth 2 -type f -name 'Singleton*' -delete || true
find "${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}" -maxdepth 1 -type f -name 'Singleton*' -delete || true
rm -f "${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}/DevToolsActivePort" || true

# ============================================================
#  OPTIONAL: FortuneCoins SB/UC specific profile handling
# ============================================================
if [ -n "${FC_USER_DATA_DIR:-}" ]; then
  mkdir -p "${FC_USER_DATA_DIR}"
  chown -R "$(id -u)":"$(id -g)" "${FC_USER_DATA_DIR}" || true
  find "${FC_USER_DATA_DIR}" -maxdepth 1 -type f -name 'Singleton*' -delete || true
fi

# ============================================================
#  START THE PYTHON APP
# ============================================================
echo "[Entrypoint] Starting CasinoClaim bot..."
echo "[Entrypoint] DISPLAY=${DISPLAY}"
echo "[Entrypoint] Chrome profile root: ${CHROME_INSTANCE_DIR}/${CHROME_PROFILE_DIR}"

exec /venv/bin/python /app/main.py
