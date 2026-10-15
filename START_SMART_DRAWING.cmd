@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "..\runtime\python\python.exe" goto bundled
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" "scripts\windows_launcher.py" start --smart-drawing
goto done
:bundled
"..\runtime\python\python.exe" "scripts\windows_launcher.py" start --smart-drawing
:done
set "catiaExit=%errorlevel%"
if "%catiaExit%"=="0" exit /b 0
echo See output above and .local\start.log.
pause
exit /b %catiaExit%
:missing
echo Run INSTALL.cmd first.
pause
exit /b 1
