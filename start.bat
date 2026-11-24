@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动码尺 CodeScale 本地服务...
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 local\server.py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python local\server.py
  ) else (
    echo 未找到 Python，请先安装 Python 3 并勾选 Add to PATH。
    pause
  )
)
pause
