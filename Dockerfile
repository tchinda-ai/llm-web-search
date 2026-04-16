# ── Base image: official Python 3.11 slim ────────────────────────────────────
FROM python:3.11-slim

# System dependencies required by crawl4ai / Playwright (Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        build-essential \
        libssl-dev \
        libffi-dev \
        libnss3 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libxshmfence1 \
        libxfixes3 \
        libatspi2.0-0 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements/requirements.txt requirements/requirements-dev.txt ./requirements/
RUN pip install --no-cache-dir \
        -r requirements/requirements.txt \
        -r requirements/requirements-dev.txt

# Install Playwright browsers (chromium is enough for headless crawling)
RUN playwright install chromium --with-deps

# Copy application source — both clients + shared core
COPY core/ ./core/
COPY app.py api.py ./

# Both ports declared; docker-compose controls which one each service uses
EXPOSE 8501 5000

# No ENTRYPOINT here — each service in docker-compose defines its own command
# so the same image can run either the Streamlit UI or the Flask REST API.
