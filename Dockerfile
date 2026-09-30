# Intrinsica — ONE image for Cloud Run: the React build is served by the FastAPI
# backend next to /api (deployment spec §2.2). Build context is the repo root.

# ---- Stage 1: build the frontend -------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Public mode: only the fake door is built in. The API base needs no arg — a
# production build calls its own origin (src/lib/api.ts).
ENV VITE_PUBLIC_MODE=1
RUN npm run build

# ---- Stage 2: the backend, serving the build -------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer is cached across code-only changes.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist /app/static

ENV INTRINSICA_STATIC_DIR=/app/static \
    PORT=8080
EXPOSE 8080

# Shell form so ${PORT} (injected by Cloud Run) is expanded. No --reload in production.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
