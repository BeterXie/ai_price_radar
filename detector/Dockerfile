FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10002 detector
WORKDIR /app
COPY probe.py worker.py ./
USER detector

CMD ["python", "worker.py"]
