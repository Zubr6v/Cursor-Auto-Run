@echo off
setlocal
cd /d "%~dp0"

if /I not "%OS%"=="Windows_NT" (
    echo This build must run on Windows.
    exit /b 1
)

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

python tools\make_icon.py
python -m PyInstaller --noconfirm --clean CursorAutoRun.spec
if errorlevel 1 exit /b 1

echo.
echo Built dist\CursorAutoRun\CursorAutoRun.exe
exit /b 0
