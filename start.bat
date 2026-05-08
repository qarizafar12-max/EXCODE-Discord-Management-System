@echo off
title Excode Bot & Dashboard Launcher
color 0b

echo ===================================================
echo     STARTING EXCODE BOT SYSTEM
echo ===================================================

echo [1/2] Starting Web Dashboard (Hidden)...
start /B python web/app.py

echo [2/2] Starting Discord Bot...
echo.
python bot.py

pause
