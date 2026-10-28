@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\local.py
if errorlevel 1 pause
