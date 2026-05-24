@echo off
REM Build batch script for packaging seamly2dk into a Windows .exe
SET PYTHON=c:\python313\python.exe
IF NOT EXIST "%PYTHON%" (
  echo Python not found at %PYTHON% - update PYTHON variable in this script.
  exit /b 1
)
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install pyinstaller
%PYTHON% -m PyInstaller --noconfirm --onefile --windowed --name seamly2dk --version-file=version_info.py main.py

echo Build finished. Check the dist\seamly2dk.exe
pause