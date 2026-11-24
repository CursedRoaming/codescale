@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动码尺 CodeScale 本地服务...
echo.

rem 优先用 PATH 里的 python；python 可用时它对应本机安装的 3.13
where python >nul 2>nul
if %errorlevel%==0 (
  python local\server.py
  goto :done
)

rem 退而求其次用 py 启动器
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 local\server.py
  goto :done
)

echo 未找到 Python，请先安装 Python 3 并勾选 Add to PATH。
pause

:done
pause
