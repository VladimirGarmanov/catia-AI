@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" "scripts\windows_launcher.py" diagnose
set "catiaExit=%errorlevel%"
echo See .local\diagnostics.log. Review paths before sharing this report.
pause
exit /b %catiaExit%
:missing
echo Run INSTALL.cmd first.
pause
exit /b 1
