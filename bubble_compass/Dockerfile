FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY bubble_compass /app/bubble_compass
COPY config /app/config
COPY scripts /app/scripts

RUN pip install --no-cache-dir -e ".[service]" || pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "bubble_compass.brain.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
