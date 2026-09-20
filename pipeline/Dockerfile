FROM python:3.13-slim
WORKDIR /workspace/pipeline
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY shared_http /tmp/shared_http
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" /tmp/shared_http \
    && pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt \
    && rm -rf /tmp/shared_http \
    && groupadd --system --gid 10001 importer \
    && useradd --system --uid 10001 --gid importer importer
COPY --chown=importer:importer pipeline/ .
# 与 crawler 数据目录保持同一 uid（10001），宿主机目录 chown 10001 后即可写入。
USER importer
CMD ["python", "sync_ldxp.py", "--help"]
