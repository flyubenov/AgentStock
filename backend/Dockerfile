# Backend container — used by Cloud Run and Railway (Render uses its native
# Python runtime via render.yaml instead). Build context is the backend/ dir.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer is cached across code-only changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Cloud Run / Railway inject $PORT at runtime; 8080 is the local `docker run` default.
ENV PORT=8080
EXPOSE 8080

# Shell form so ${PORT} is expanded. 0.0.0.0 is required for the container to be
# reachable. No --reload in production.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
