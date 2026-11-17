FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AGENTS_DIR=/app/agents \
    SERVE_WEB_UI=true

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY agents ./agents
COPY deployment/__init__.py ./deployment/__init__.py
COPY deployment/cloud_run ./deployment/cloud_run

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn deployment.cloud_run.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
