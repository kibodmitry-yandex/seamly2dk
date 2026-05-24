@echo off
REM Build batch script for packaging seamly2dk into a Windows .exe
SET PYTHON=c:\python313\python.exe
IF NOT EXIST "%PYTHON%" (
  echo Python not found at %PYTHON% - update PYTHON variable in this script.
  exit /b 1
)
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install pyinstaller
%PYTHON% -m PyInstaller --noconfirm --onefile --windowed --name seamly2dk main.py

REM after build: apply rcedit to embed version strings
set "DIST_EXE=%CD%\dist\seamly2dk.exe"
set "RCEDIT=%CD%\build\seamly2dk\rcedit-x64.exe"
if not exist "%RCEDIT%" (
  echo rcedit not found, attempting to download...
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/electron/rcedit/releases/download/v1.1.1/rcedit-x64.exe' -OutFile '%RCEDIT%'"
)
if exist "%RCEDIT%" if exist "%DIST_EXE%" (
  REM write metadata JSON to temp file
  %PYTHON% -c "import json,release_meta; print(json.dumps({'ver':release_meta.VERSION,'author':release_meta.AUTHOR,'year':release_meta.YEAR,'url':release_meta.URL,'desc':release_meta.FILEDESC}))" > "%TEMP%\\seamly_meta.json"
  REM call python to invoke rcedit using the temp JSON
  %PYTHON% -c "import json,subprocess; j=json.load(open(r'%TEMP%\\seamly_meta.json')); ver=j['ver']+'.0'; cmd=[r'%RCEDIT%', r'%DIST_EXE%', '--set-file-version', ver, '--set-product-version', ver, '--set-version-string', 'CompanyName', j['author'], '--set-version-string', 'FileDescription', j['desc'], '--set-version-string', 'LegalCopyright', '(c) '+str(j['year'])+' '+j['author'], '--set-version-string', 'OriginalFilename', 'seamly2dk.exe', '--set-version-string', 'ProductName', 'seamly2dk', '--set-version-string', 'Comments', j['url']]; subprocess.check_call(cmd); print('Applied resource strings.')"
  del "%TEMP%\\seamly_meta.json"
)

echo Build finished. Check the dist\seamly2dk.exe
pause
pause