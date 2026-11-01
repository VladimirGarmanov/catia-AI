@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "..\runtime\python\python.exe" goto bundled
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" "scripts\windows_launcher.py" diagnose --client claude
goto done
:bundled
"..\runtime\python\python.exe" "scripts\windows_launcher.py" diagnose --client claude
:done
set "catiaExit=%errorlevel%"
echo See .local\diagnostics.log. Review paths before sharing.
pause
exit /b %catiaExit%
:missing
echo Run INSTALL.cmd first.
pause
exit /b 1
