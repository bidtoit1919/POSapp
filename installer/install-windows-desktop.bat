@echo off
setlocal
for %%I in ("%~dp0..\ShopPOS\ShopPOS.exe") do set "APP_EXE=%%~fI"
if not exist "%APP_EXE%" (
  echo ShopPOS.exe was not found. The installer folder and ShopPOS folder must be together inside dist.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create-windows-shortcut.ps1" "%APP_EXE%"
if errorlevel 1 (
  echo ShopPOS desktop shortcut could not be created.
  pause
  exit /b 1
)
echo ShopPOS is installed. A desktop shortcut was created and the application will open now.
start "" "%APP_EXE%"
timeout /t 3 /nobreak >nul
