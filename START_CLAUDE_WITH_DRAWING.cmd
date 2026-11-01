@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
call START_CLAUDE_AI.cmd --choose-drawing
exit /b %errorlevel%
