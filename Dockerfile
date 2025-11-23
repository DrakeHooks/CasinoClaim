# 1) Base image
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 2) System deps + Chrome
RUN apt-get update && apt-get install -y \
    xvfb x11vnc fluxbox x11-apps x11-utils \
    wget curl gnupg2 ca-certificates apt-transport-https \
    python3 python3-venv xdg-utils locales \
    python3-tk python3-dev python3-xlib scrot xclip xsel wmctrl \
    libx11-6 libxext6 libxrender1 libxfixes3 libxi6 libsm6 libxrandr2 \
    libxcb1 libxkbcommon0 libxtst6 gnome-screenshot \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

RUN rm -rf /etc/opt/chrome/policies || true

# 3) App directory
WORKDIR /app

# (A) Requirements first → cache
COPY requirements.txt /app/requirements.txt

# 4) Python env with uv
ENV PATH="/root/.local/bin:${PATH}"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    uv venv /venv && \
    uv pip install --python /venv/bin/python -r /app/requirements.txt

ENV PATH="/venv/bin:${PATH}"

# 5) COPY ALL SOURCE FILES
COPY . /app

# 6) CRX explicitly copied (your compose mounts it too)
COPY CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx /temp/CAPTCHA-Solver.crx

# 7) Entrypoint
RUN chmod +x /app/entrypoint.sh

ENV DISPLAY=:99
ENV CHROME_USER_DATA_DIR=/data/chrome
ENV CHROME_PROFILE_DIR=Default

ENTRYPOINT ["/bin/bash","-lc","/app/entrypoint.sh"]
