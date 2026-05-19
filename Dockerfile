# ---- frontend stage (stubbed; populated in Plan 3) ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
RUN mkdir -p dist && echo '<!doctype html><title>Halite</title>' > dist/index.html

# ---- python runtime ----
FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/src /app/backend/src
RUN pip install --no-cache-dir /app/backend

COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/alembic /app/backend/alembic
COPY --from=frontend /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn halite.main:create_app --factory --host 0.0.0.0 --port 8080"]
