FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "prm.api"]
