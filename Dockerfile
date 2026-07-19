# ============================================
# DD Planner — Multi-stage Docker Build
# Stage 1: Build React frontend
# Stage 2: Production runtime (Python + Nginx)
# ============================================

# ---------- Stage 1: Frontend build ----------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile --production=false

COPY frontend/ .

ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}
ENV DISABLE_ESLINT_PLUGIN=true

RUN yarn build


# ---------- Stage 2: Production runtime ----------
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor curl \
        # Playwright/Chromium runtime deps
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
        libcairo2 libasound2 fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/

# Install Playwright Chromium for PDF/PPT exports (bundled into image so first
# request doesn't have to download ~110MB at runtime)
ENV PLAYWRIGHT_BROWSERS_PATH=/pw-browsers
RUN python -m playwright install chromium

# Backend source
COPY backend/ ./backend/

# Frontend build artifacts
COPY --from=frontend-build /app/frontend/build /app/frontend/build

# Config files
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
