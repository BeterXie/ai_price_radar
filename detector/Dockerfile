FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10002 detector
WORKDIR /app
COPY shared_http /tmp/shared_http
COPY detector/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir /tmp/shared_http -r requirements.txt \
    && rm -rf /tmp/shared_http
COPY detector/probe.py detector/qualify.py detector/sitemap.py detector/worker.py ./
COPY pipeline/currencies.py ./currencies.py
COPY apps/api/app/services/classifier.py ./classifier.py
USER detector

CMD ["python", "worker.py"]
