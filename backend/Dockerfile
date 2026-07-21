FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/state/radar.db

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY entrypoint.py ./entrypoint.py
RUN pip install --no-cache-dir .

RUN addgroup --system radar && adduser --system --ingroup radar radar \
    && mkdir -p /state && chown -R radar:radar /state /app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["python", "/app/entrypoint.py"]
