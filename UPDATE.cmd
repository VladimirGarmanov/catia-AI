@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "..\runtime\python\python.exe" goto bundled
if exist ".venv\Scripts\python.exe" goto venv
echo Python runtime was not found. Run INSTALL.cmd once, then UPDATE.cmd.
pause
exit /b 1
:bundled
"..\runtime\python\python.exe" "scripts\update_project.py"
goto done
:venv
".venv\Scripts\python.exe" "scripts\update_project.py"
:done
set "catiaExit=%errorlevel%"
echo.
echo Update exit code: %catiaExit%
pause
exit /b %catiaExit%
