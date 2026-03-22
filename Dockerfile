FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* readme.md ./

RUN pip install --no-cache-dir poetry==1.8.5

RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
