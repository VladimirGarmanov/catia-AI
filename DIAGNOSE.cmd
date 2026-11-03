@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
if exist "..\runtime\python\python.exe" goto bundled
echo Run INSTALL.cmd first.
pause
exit /b 1
:venv
".venv\Scripts\python.exe" "scripts\windows_launcher.py" diagnose %*
goto done
:bundled
"..\runtime\python\python.exe" "scripts\windows_launcher.py" diagnose %*
:done
set "catiaExit=%errorlevel%"
echo See .local\diagnostics.log for details.
pause
exit /b %catiaExit%
