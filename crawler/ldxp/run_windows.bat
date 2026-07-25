@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py -3
) else (
  set PY=python
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] 创建 Python 虚拟环境...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"

echo [2/4] 安装 Python 依赖...
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

echo [3/4] 安装 Chromium（首次会下载，后续会跳过已有文件）...
python -m playwright install chromium
if errorlevel 1 goto :error

echo [4/4] 开始发现、浏览器扫描并导出...
echo 首次出现验证页时，请在自动打开的 Chromium 窗口中正常完成验证。
python ldxp_gpt_crawler.py all ^
  --keywords gpt chatgpt openai codex "gpt plus" "gpt team" ^
  --seed-file seeds.txt ^
  --sources seed,bing,commoncrawl ^
  --bing-pages 5 ^
  --cc-indexes 3 ^
  --request-interval 2.0 ^
  --retry-blocked ^
  --circuit-breaker 3

if errorlevel 1 goto :error

echo.
echo 完成。结果位于 output 文件夹；浏览器会话保存在 browser_profile。
pause
exit /b 0

:error
echo.
echo 运行失败，请查看上方错误。
pause
exit /b 1
