FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10002 detector
WORKDIR /app
COPY shared_http /tmp/shared_http
RUN pip install --no-cache-dir /tmp/shared_http \
    && rm -rf /tmp/shared_http
COPY detector/probe.py detector/qualify.py detector/worker.py ./
COPY apps/api/app/services/classifier.py ./classifier.py
USER detector

CMD ["python", "worker.py"]
