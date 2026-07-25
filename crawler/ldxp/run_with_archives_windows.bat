@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 run_windows.bat 完成安装。
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python ldxp_gpt_crawler.py all ^
  --keywords gpt chatgpt openai codex ^
  --seed-file seeds.txt ^
  --sources seed,bing,commoncrawl,wayback ^
  --request-interval 2.5 ^
  --retry-blocked ^
  --circuit-breaker 3
pause
