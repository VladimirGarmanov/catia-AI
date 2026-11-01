@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "..\runtime\python\python.exe" goto bundled
call INSTALL.cmd --client claude
exit /b %errorlevel%
:bundled
"..\runtime\python\python.exe" "scripts\windows_launcher.py" install --client claude
set "catiaExit=%errorlevel%"
pause
exit /b %catiaExit%
