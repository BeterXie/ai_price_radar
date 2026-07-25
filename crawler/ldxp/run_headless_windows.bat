@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 run_windows.bat 完成安装和首次浏览器验证。
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python ldxp_gpt_crawler.py all ^
  --headless ^
  --keywords gpt chatgpt openai codex "gpt plus" "gpt team" ^
  --seed-file seeds.txt ^
  --sources seed,bing,commoncrawl ^
  --request-interval 2.0 ^
  --circuit-breaker 3
pause
