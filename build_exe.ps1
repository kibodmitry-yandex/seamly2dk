# Build PowerShell script for packaging seamly2dk into a Windows .exe
# Usage: Open Developer PowerShell and run: .\build_exe.ps1

$python = "c:/python313/python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Python executable not found at $python. Update the path in this script."
    exit 1
}
# upgrade pip
& $python -m pip install --upgrade pip
# install pyinstaller
& $python -m pip install pyinstaller
# run pyinstaller onefile build (windowed to hide console)
& $python -m PyInstaller --noconfirm --onefile --windowed --name seamly2dk --version-file=version_info.py main.py

Write-Host "Build finished. Check the 'dist' folder for seamly2dk.exe"