FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY etl ./etl
COPY vocabularies ./vocabularies

RUN pip install --upgrade pip && pip install -e '.[dev]'

CMD ["python", "-m", "etl.extract"]
