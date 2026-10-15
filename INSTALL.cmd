@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
if exist ".local\python\python.exe" goto localpython
where py.exe >nul 2>nul
if errorlevel 1 goto checkpython
py.exe -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 goto py
:checkpython
where python.exe >nul 2>nul
if errorlevel 1 goto bootstrap
python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 goto python
goto bootstrap
:localpython
".local\python\python.exe" "scripts\windows_launcher.py" install
goto done
:bootstrap
echo Python was not found. Downloading the official Python 3.13.3 x64 installer.
echo Installation is per-user inside this project's .local folder. No administrator rights or PATH changes.
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto downloadpython
if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto downloadpython
echo STOP: Automatic Python bootstrap currently supports Windows x64 only. Use the packaged installer or contact IT.
goto failed
:downloadpython
if not exist ".local\downloads" mkdir ".local\downloads"
if errorlevel 1 goto failed
set "CATIA_PY_INSTALLER=%CD%\.local\downloads\python-3.13.3-amd64.exe"
curl.exe --fail --show-error --location --proto =https --proto-redir =https --max-time 300 --output "%CATIA_PY_INSTALLER%" "https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe"
if errorlevel 1 goto failed
echo Verifying the Python Software Foundation digital signature before execution.
powershell.exe -NoProfile -NonInteractive -Command "$s = Get-AuthenticodeSignature -LiteralPath $env:CATIA_PY_INSTALLER; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(,|$)') { Write-Error 'Python installer signature validation failed'; exit 1 }"
if errorlevel 1 goto failed
start "" /wait "%CATIA_PY_INSTALLER%" /quiet /norestart InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_pip=1 Include_tcltk=1 Shortcuts=0 TargetDir="%CD%\.local\python" /log "%CD%\.local\python-install.log"
if errorlevel 1 goto failed
if exist ".local\python\python.exe" goto localpython
:failed
echo STOP: Automatic installation could not finish. Check network access or contact IT.
echo No administrator rights were requested. Security policies and file blocking were not changed.
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
