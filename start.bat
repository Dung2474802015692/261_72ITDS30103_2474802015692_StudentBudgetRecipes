@echo off
rem Double-click to run. First run creates .venv and installs dependencies (needs Python 3.12 and internet once).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || (echo Python 3 is required: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
.venv\Scripts\python -u run.py
pause
