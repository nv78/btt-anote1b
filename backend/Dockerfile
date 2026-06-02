# ── Stage 1: install dependencies ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: production image ──────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code (see .dockerignore for exclusions)
COPY . .

# Non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PORT=5000
ENV FLASK_ENV=production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
