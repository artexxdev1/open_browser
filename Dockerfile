# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS builder

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime

RUN groupadd --system automation \
    && useradd --system --gid automation --create-home automation

COPY --from=builder /install /usr/local
COPY app ./app
COPY storage ./storage

RUN mkdir -p storage/logs \
    && chown -R automation:automation /app

USER automation

EXPOSE 8000

CMD ["python", "-m", "app.main"]
