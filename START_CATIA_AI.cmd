@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" "scripts\windows_launcher.py" start
set "catiaExit=%errorlevel%"
if "%catiaExit%"=="0" exit /b 0
echo See .local\start.log for details.
pause
exit /b %catiaExit%
:missing
echo Run INSTALL.cmd first.
pause
exit /b 1
