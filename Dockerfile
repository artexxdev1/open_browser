# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY storage ./storage

RUN mkdir -p storage/logs \
    && useradd --system --create-home automation \
    && chown -R automation:automation /app

USER automation

EXPOSE 8000

CMD ["python", "-m", "app.main"]
