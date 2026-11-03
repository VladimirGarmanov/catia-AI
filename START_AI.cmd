@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
if exist "..\runtime\python\python.exe" goto bundled
echo Run INSTALL.cmd first.
pause
exit /b 1
:venv
".venv\Scripts\python.exe" "scripts\windows_launcher.py" start %*
goto done
:bundled
"..\runtime\python\python.exe" "scripts\windows_launcher.py" start %*
:done
set "catiaExit=%errorlevel%"
if "%catiaExit%"=="0" exit /b 0
echo See .local\start.log for details.
pause
exit /b %catiaExit%
