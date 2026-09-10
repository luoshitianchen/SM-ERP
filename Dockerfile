# 多阶段构建: SM Service
FROM python:3.11-slim AS builder
WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /install /install
ENV PYTHONPATH=/install/lib/python3.11/site-packages
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
USER appuser
EXPOSE 8300
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8300/readyz')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8300", "--no-server-header"]
