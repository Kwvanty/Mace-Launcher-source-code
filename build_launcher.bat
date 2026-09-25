@echo off
setlocal

python -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

python -m PyInstaller MaceLauncher.spec
if errorlevel 1 exit /b %errorlevel%

echo.
echo Build complete.
pause
