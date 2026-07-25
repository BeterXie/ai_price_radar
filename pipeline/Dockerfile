FROM python:3.13-slim
WORKDIR /workspace/pipeline
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "sync_ldxp.py", "--help"]
