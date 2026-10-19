@echo off
chcp 65001 >nul
title CloudStorage Control

echo ============================================
echo     CloudStorage Server Control
echo ============================================
echo.

echo Checking server status...

tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul

if %ERRORLEVEL% EQU 0 (
    echo Server is RUNNING
    echo.
    echo Stopping server...
    taskkill /f /im python.exe >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Server stopped successfully
    ) else (
        echo [ERROR] Failed to stop server
    )
) else (
    echo Server is NOT running
    echo.
    echo Starting server...
    cd /d "C:\Users\admsys\PycharmProjects\CloudStorage"
    start "" "C:\Users\admsys\PycharmProjects\CloudStorage\.venv\Scripts\python.exe" "C:\Users\admsys\PycharmProjects\CloudStorage\app.py"
    echo [OK] Server starting...
)

echo.
timeout /t 2 /nobreak >nul