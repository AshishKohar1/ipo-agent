@echo off
REM Read-only progress for the SEBI download / RHP extraction chain.
REM Safe to double-click at any time: it reads files and lists processes, and
REM never touches the running job.
setlocal
cd /d "%~dp0"
python watch_progress.py
echo.
echo Press any key to close, or run this again for an updated rate.
pause >nul
