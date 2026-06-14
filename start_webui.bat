@echo off
chcp 65001 >nul
echo ========================================
echo   OpenAgent Web UI
echo ========================================
echo.
echo 1. 设置 API Key（选一个即可）:
echo    set DEEPSEEK_API_KEY=sk-your-key
echo    set OPENAI_API_KEY=sk-your-key
echo.
echo 2. 启动后访问 http://127.0.0.1:8080
echo.
echo 正在启动...
pause >nul

cd /d "%~dp0"
python web_ui\main.py
pause
