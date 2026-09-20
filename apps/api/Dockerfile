FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
# 构建上下文是仓库根目录（compose 中 context: .），这样才能把 extensions/ 一起打进镜像，
# 否则 main.py 启动时的 QQ Gateway 导入会静默失败。
COPY apps/api/requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt
RUN addgroup --system app && adduser --system --ingroup app app
COPY --chown=app:app apps/api/app ./app
COPY --chown=app:app extensions ./extensions

EXPOSE 8000
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
