@echo off
title ReviewFlow Telegram Automation Engine
chcp 65001 > nul
cd /d D:\MassgesReview
set PYTHONPATH=D:\MassgesReview
set PYTHONUNBUFFERED=1

echo ======================================================================
echo   ReviewFlow Telegram Automation Platform
echo ======================================================================
echo [*] Starting Services...
python -u start_all.py
pause
