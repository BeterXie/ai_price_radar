@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
  copy .env.example .env >nul
  echo 已创建 .env。正式上线前请修改密码和管理密钥。
)

docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
if errorlevel 1 goto :error

echo.
echo 前台: http://localhost:3000
echo 后台: http://localhost:3000/admin
echo API文档: http://localhost:8000/docs
pause
exit /b 0

:error
echo 启动失败，请确认 Docker Desktop 已启动。
pause
exit /b 1
