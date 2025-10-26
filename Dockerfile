# Use Ubuntu 22.04 as the base image
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# … keep what you already have …
RUN apt-get update && apt-get install -y \
    xvfb x11vnc fluxbox x11-apps x11-utils \
    wget gnupg2 ca-certificates apt-transport-https \
    python3 python3-venv python3-pip xdg-utils locales \
    # GUI automation deps
    python3-tk python3-dev python3-xlib scrot xclip xsel wmctrl \
    # X11 libs Pillow/ImageGrab relies on
    libx11-6 libxext6 libxrender1 libxfixes3 libxi6 libsm6 libxrandr2 \
    libxcb1 libxkbcommon0 libxtst6 \
    # Screenshot backend requested by Pillow/pyscreeze
    gnome-screenshot \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*



# 2) Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# (Optional) remove enterprise policies
RUN rm -rf /etc/opt/chrome/policies /etc/chromium/policies || true

# 3) App files
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY main.py /app/main.py
# If you need the crx available to Python, keep this:
COPY CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx /temp/CAPTCHA-Solver.crx

# 4) Python env
RUN python3 -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r /app/requirements.txt && \
    /venv/bin/pip install --no-cache-dir brotli

ENV PATH="/venv/bin:${PATH}"

# 5) Entrypoint script (handles X locks + VNC + unique user-data-dir)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 6) Defaults for headed Chrome
ENV DISPLAY=:99
# Root for persistent Chrome profiles; compose will mount a volume here
ENV CHROME_USER_DATA_DIR=/data/chrome
ENV CHROME_PROFILE_DIR=Default

ENTRYPOINT ["/bin/bash","-lc","/app/entrypoint.sh"]
