# Use Ubuntu 22.04 as the base image
FROM ubuntu:latest

# Install necessary packages
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    wget \
    unzip \
    gnupg2 \
    software-properties-common \
    apt-utils \
    ca-certificates \
    curl \
    python3 \
    python3-venv \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install uv for managing Python dependencies
RUN curl -Ls https://astral.sh/uv/install.sh | bash

# Install Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory to the root of the project
WORKDIR /app

# Copy the .crx file to a temporary directory
COPY ./CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx /temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx

# Copy the google-chrome directory to a temporary directory
# COPY ./google-chrome /temp/google-chrome

# Copy the entire project to /app in the container
COPY . /app

# Create virtual environment and install Python dependencies using uv
RUN python3 -m venv /venv && \
    /venv/bin/uv pip install --no-cache-dir -r /app/requirements.txt

# Install common utilities
RUN apt-get update && apt-get install -y xdg-utils ca-certificates

# Ensure the lock file is removed on every container start
RUN echo '#!/bin/bash\nrm -f /tmp/.X99-lock\nexec "$@"' > /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh

# Set environment variables
ENV PATH="/venv/bin:$PATH"
ENV DISPLAY=:99

# Start Xvfb, fluxbox, and x11vnc, ensuring no lock conflicts
CMD ["/usr/local/bin/docker-entrypoint.sh", "bash", "-c", "Xvfb :99 -screen 0 1920x1080x24 & fluxbox & x11vnc -forever -usepw -create -display :99 & /venv/bin/python /app/main.py"]
