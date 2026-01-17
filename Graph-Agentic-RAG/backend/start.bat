@echo off
chcp 65001 >nul
echo ================================
echo Graph RAG Agent - Backend Server
echo ================================
echo.

REM 加载环境变量
for /f "tokens=1,* delims==" %%a in (.env) do (
    set "%%a=%%b"
)

echo Using API: %MINIMAX_API_URL%
echo Using Model: %MINIMAX_MODEL%
echo.

REM 检查API Key
if "%MINIMAX_API_KEY%"=="" (
    echo [ERROR] MINIMAX_API_KEY is not set!
    echo Please edit .env file and add your API key.
    pause
    exit /b 1
) else (
    echo [OK] API Key is configured
)

echo.
echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop
echo.

REM 启动服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
