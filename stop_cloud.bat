@echo off
chcp 65001 >nul
title Stop CloudStorage

echo ============================================
echo     Stopping CloudStorage Server
echo ============================================
echo.

echo Searching for Python processes...
echo.

taskkill /f /im python.exe

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Server stopped successfully
) else (
    echo.
    echo [INFO] Server not found or already stopped
)

echo.
timeout /t 3 /nobreak >nul