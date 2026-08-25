@echo off
title Creature Lab
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
if errorlevel 1 (
  echo.
  echo Creature Lab did not start. Review the error above.
  pause
)
