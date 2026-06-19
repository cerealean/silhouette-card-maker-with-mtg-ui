@echo off
REM Double-click this file (Windows) to set up and launch the Card Maker UI.
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required but was not found. Please install it from https://www.python.org/downloads/
  echo Be sure to check "Add Python to PATH" during installation.
  pause
  exit /b 1
)
python "%~dp0run.py"
pause
