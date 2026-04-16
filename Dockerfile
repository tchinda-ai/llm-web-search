# ── Base image: official Python 3.11 slim ────────────────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Define where Playwright should store its browsers (system-wide)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Create a non-root user & group with a valid home directory
RUN addgroup --system appgroup && \
    adduser --system --group --home /home/appuser appuser && \
    mkdir -p /home/appuser && \
    chown -R appuser:appgroup /home/appuser

# Enable APT caching in BuildKit
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# System dependencies required by crawl4ai / Playwright
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
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
        fonts-liberation

WORKDIR /app

# Directories ownership for the non-root user
RUN mkdir -p /app /ms-playwright && chown -R appuser:appgroup /app /ms-playwright

# Install Python dependencies (Using BuildKit cache to speed up pip installs)
COPY requirements/requirements.txt requirements/requirements-dev.txt ./requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/requirements.txt -r requirements/requirements-dev.txt

# Install Playwright browsers (chromium only) & ensure correct permissions
RUN playwright install chromium --with-deps && chmod -R 775 /ms-playwright

# Downgrade to non-root user BEFORE copying the application code
USER appuser

# Copy application source (Changes here will NOT invalidate the Playwright install)
COPY --chown=appuser:appgroup core/ ./core/
COPY --chown=appuser:appgroup app.py api.py ./

EXPOSE 8501 5005
