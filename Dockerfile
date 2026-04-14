# ── Base image: official Python 3.11 slim ────────────────────────────────────
FROM python:3.11-slim

# System dependencies required by crawl4ai / unstructured / Playwright
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

# Copy and install Python dependencies first (better layer caching)
COPY requirements/requirements.txt requirements/requirements-dev.txt ./requirements/

RUN pip install --no-cache-dir \
        -r requirements/requirements.txt \
        -r requirements/requirements-dev.txt

# Install Playwright browsers (chromium is enough for headless crawling)
RUN playwright install chromium --with-deps

# Copy application source
COPY app.py .

EXPOSE 8501

# Streamlit health-check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0"]
