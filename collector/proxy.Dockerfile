FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 gateway
COPY shared_http /tmp/shared_http
RUN pip install --no-cache-dir --no-deps /tmp/shared_http && rm -rf /tmp/shared_http
COPY collector/proxy_gateway.py ./
USER gateway
CMD ["python", "proxy_gateway.py"]
