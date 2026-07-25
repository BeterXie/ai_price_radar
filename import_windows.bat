@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ldxp_crawler.db (
  echo 未找到 ldxp_crawler.db，请先把爬虫数据库复制到项目根目录。
  pause
  exit /b 1
)

docker compose --profile tools run --rm importer python sync_ldxp.py ^
  --source-db /workspace/ldxp_crawler.db

pause
