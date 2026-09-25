@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
where py.exe >nul 2>nul
if not errorlevel 1 goto py
where python.exe >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.10+ is required. Ask IT if software installation is restricted.
pause
exit /b 1
:venv
".venv\Scripts\python.exe" "scripts\windows_launcher.py" install
goto done
:py
py.exe -3 "scripts\windows_launcher.py" install
goto done
:python
python.exe "scripts\windows_launcher.py" install
:done
set "catiaExit=%errorlevel%"
echo.
echo Exit code: %catiaExit%. See .local\setup.log for details.
pause
exit /b %catiaExit%
