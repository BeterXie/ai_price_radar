@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 run_windows.bat，或手动安装 requirements.txt 和 Chromium。
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo 将打开 seeds.txt 中的第一家店铺，用于建立或刷新浏览器验证会话。
python ldxp_gpt_crawler.py bootstrap --manual-challenge-seconds 600
pause
