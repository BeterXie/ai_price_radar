FROM python:3.13-slim
WORKDIR /workspace/pipeline
COPY shared_http /tmp/shared_http
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir /tmp/shared_http \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /tmp/shared_http
COPY pipeline/ .
CMD ["python", "sync_ldxp.py", "--help"]
