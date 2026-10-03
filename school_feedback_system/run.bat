@echo off
title School Teacher Feedback System
echo ========================================================
echo Starting School Teacher Feedback & Evaluation System
echo ========================================================
echo.

cd /d "%~dp0"

echo Checking and installing dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo Starting Streamlit Web Application on port 8501...
echo Open your web browser at: http://localhost:8501
echo.
python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0

pause
