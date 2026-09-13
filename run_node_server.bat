@echo off
title ESP32 NFC Wi-Fi Music Server (Node.js)
color 0A
cd /d "%~dp0\server_node"

echo ========================================================
echo     ESP32 NFC WI-FI MUSIC SERVER (NODE.JS LAUNCHER)
echo ========================================================
echo.

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Node.js is not installed or not in your system PATH!
    echo Please install Node.js from https://nodejs.org/
    echo.
    pause
    exit /b
)

:: Install dependencies if node_modules missing
if not exist "node_modules" (
    echo [*] Installing Node.js packages (express)...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install npm packages.
        pause
        exit /b
    )
)

echo.
echo ========================================================
echo  [IMPORTANT] LOOK BELOW FOR YOUR PC'S LOCAL IP ADDRESS:
echo ========================================================
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "0.0.0.0.0"') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip
echo  -> Your PC's Wi-Fi IP Address: %LOCAL_IP%
echo  -> Put this IP in your ESP32 Arduino code:
echo     const char* SERVER_IP = "%LOCAL_IP%";
echo ========================================================
echo.
echo Starting Node.js Music Server...
echo (Press Ctrl+C to stop the server at any time)
echo.

node server.js

if %errorlevel% neq 0 (
    echo.
    echo [SERVER STOPPED WITH ERROR]
    pause
)
