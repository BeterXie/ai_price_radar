FROM mcr.microsoft.com/playwright/python:v1.61.0-noble
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HOME=/home/collector XDG_CONFIG_HOME=/tmp/xdg-config XDG_CACHE_HOME=/tmp/xdg-cache
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY crawler/ldxp/requirements.txt /tmp/requirements.txt
COPY collector/requirements.txt /tmp/collector-requirements.txt
RUN mkdir -p /tmp/xdg-config /tmp/xdg-cache && pip install --no-cache-dir playwright==1.61.0 -r /tmp/requirements.txt -r /tmp/collector-requirements.txt \
    && useradd --create-home --uid 10001 collector
COPY shared_http /tmp/shared_http
RUN pip install --no-cache-dir --no-deps /tmp/shared_http
COPY crawler/ldxp/ldxp_gpt_crawler.py ./
COPY crawler/ldxp/ldxp_crawler ./ldxp_crawler
COPY pipeline/connectors ./connectors
COPY pipeline/currencies.py pipeline/storefront_catalog.py ./
COPY apps/api/app/services/collector_protocol.py ./
COPY collector/worker.py ./collector_worker.py
COPY collector/source_cache.py ./source_cache.py
COPY config/collection-keywords.json ./
USER collector
CMD ["python", "collector_worker.py"]
