FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080 \
    PANTRY_ROOT=/app PANTRY_MODEL=/app/models/yolo-world-s-pantry.onnx
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && rm -rf src
COPY config ./config
# Fetched from the private models bucket by the first Cloud Build step, never committed.
COPY models/yolo-world-s-pantry.onnx models/yolo-world-s-pantry.json ./models/

RUN useradd --create-home --uid 10001 pantry
USER pantry

CMD exec uvicorn pantry.main:app --host 0.0.0.0 --port "$PORT"
