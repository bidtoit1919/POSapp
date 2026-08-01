@echo off
setlocal
set "APP_EXE=%~dp0..\ShopPOS\ShopPOS.exe"
if not exist "%APP_EXE%" (
  echo ShopPOS.exe was not found next to this installer.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create-windows-shortcut.ps1" "%APP_EXE%"
if errorlevel 1 pause
