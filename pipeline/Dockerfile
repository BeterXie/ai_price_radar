FROM python:3.13-slim
WORKDIR /workspace/pipeline
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY shared_http /tmp/shared_http
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" /tmp/shared_http \
    && pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt \
    && rm -rf /tmp/shared_http
COPY pipeline/ .
CMD ["python", "sync_ldxp.py", "--help"]
