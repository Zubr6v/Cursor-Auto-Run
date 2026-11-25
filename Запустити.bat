@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title Cursor Auto Run

if /I not "%OS%"=="Windows_NT" (
  echo This file starts only on Windows.
  pause
  exit /b 1
)

if exist "%~dp0dist\CursorAutoRun\CursorAutoRun.exe" (
  start "" "%~dp0dist\CursorAutoRun\CursorAutoRun.exe"
  exit /b 0
)

call :find_python
if not defined CREATE goto :no_python

set "VENV=%~dp0.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PYTHONW=%VENV%\Scripts\pythonw.exe"

if not exist "%PYTHON%" goto :install
"%PYTHON%" -c "import PySide6" >nul 2>&1
if errorlevel 1 goto :install
goto :launch

:install
echo Перший запуск: встановлюю компоненти. Зачекайте, вікно відкриється саме.
%CREATE% -m venv "%VENV%"
if errorlevel 1 goto :venv_failed
"%PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto :pip_failed

:launch
if not exist "%PYTHONW%" set "PYTHONW=%PYTHON%"
start "" "%PYTHONW%" -m cursor_auto_run
exit /b 0

:no_python
echo Потрібен Python 3.12 або новіший.
echo Завантажте його з https://www.python.org/downloads/
echo Під час встановлення позначте Add python.exe to PATH.
echo Після цього знову відкрийте цей файл.
pause
exit /b 1

:venv_failed
echo Не вдалося створити середовище Python.
pause
exit /b 1

:pip_failed
echo Не вдалося встановити компоненти. Перевірте інтернет і відкрийте файл ще раз.
pause
exit /b 1

:find_python
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1
if errorlevel 1 goto :try_py3
set "CREATE=py -3.12"
goto :eof
:try_py3
py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1
if errorlevel 1 goto :try_python
set "CREATE=py -3"
goto :eof
:try_python
python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1
if errorlevel 1 goto :eof
set "CREATE=python"
goto :eof
