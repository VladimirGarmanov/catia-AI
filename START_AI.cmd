@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
echo CATIA AI - choose ONE client for this CATIA session.
echo 1. Codex
echo 2. Claude Code
choice /c 12 /n /m "Choose 1 or 2: "
if errorlevel 2 goto claude
call START_CATIA_AI.cmd
exit /b %errorlevel%
:claude
call START_CLAUDE_AI.cmd
exit /b %errorlevel%
