FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* ./
COPY persola/ ./persola/
COPY alembic/ ./alembic/
COPY docs/ ./docs/
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir --break-system-packages poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main \
    && chmod +x /entrypoint.sh \
    && ln -sf /app/alembic/alembic.ini /app/alembic.ini || true

EXPOSE 8002

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "persola.api.main:app", "--host", "0.0.0.0", "--port", "8002"]
