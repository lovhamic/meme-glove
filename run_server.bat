@echo off
title ESP32 NFC Wi-Fi Music Server
color 0B
cd /d "%~dp0\server"

echo ========================================================
echo        ESP32 NFC WI-FI MUSIC SERVER LAUNCHER
echo ========================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.8+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

:: Check or create virtual environment
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install / verify dependencies
echo [*] Checking dependencies (Flask, Pygame)...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [!] Pip install encountered an issue, trying verbose install...
    pip install -r requirements.txt
)

:: Generate sample sounds if none exist
python generate_samples.py

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
echo Starting Python Music Server...
echo (Press Ctrl+C to stop the server at any time)
echo.

python server.py

if %errorlevel% neq 0 (
    echo.
    echo [SERVER STOPPED WITH ERROR]
    pause
)
