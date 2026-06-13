@echo off
chcp 65001 >nul
echo ========================================
echo   OpenAgent Web UI
echo ========================================
echo.
echo 1. 设置你的 API Key（选一个）:
echo    set DEEPSEEK_API_KEY=sk-your-key
echo    set OPENAI_API_KEY=sk-your-key
echo.
echo 2. 启动后浏览器访问 http://127.0.0.1:8080
echo.
echo 按任意键启动...
pause >nul

cd /d "%~dp0"
python web_ui\main.py
pause
