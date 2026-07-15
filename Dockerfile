FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/ ./packages/
COPY agents/ ./agents/
COPY landing/ ./landing/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/
COPY database/ ./database/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "packages.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
