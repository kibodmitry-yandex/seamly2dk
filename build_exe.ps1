<# Build PowerShell script for packaging seamly2dk into a Windows .exe
   Usage: run .\build_exe.ps1 from the project root (Developer PowerShell recommended)
#>

<# Choose Python executable:
   1) prefer active virtualenv ($env:VIRTUAL_ENV) if present
   2) else use `python` found on PATH
   3) fall back to hard-coded c:/python313/python.exe (edit if needed)
#>
$python = $null
if ($env:VIRTUAL_ENV) {
    $venv_python = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
    if (Test-Path $venv_python) { $python = $venv_python }
}
if (-not $python) {
    $pycmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pycmd -and $pycmd.Path -and (Test-Path $pycmd.Path)) { $python = $pycmd.Path }
}
if (-not $python) { $python = 'c:/python313/python.exe' }
if (-not (Test-Path $python)) {
    Write-Error "Python executable not found at $python. Update the path in this script or activate your virtualenv."
    exit 1
}

# upgrade pip and install pyinstaller
& $python -m pip install --upgrade pip
& $python -m pip install pyinstaller

# run pyinstaller onefile build (windowed to hide console)
& $python -m PyInstaller --noconfirm --onefile --windowed --name seamly2dk main.py

# after build: apply version/resource strings via rcedit
$distExe = Join-Path $PSScriptRoot 'dist\seamly2dk.exe'
$rcedit = Join-Path $PSScriptRoot 'build\seamly2dk\rcedit-x64.exe'
if (-not (Test-Path $rcedit)) {
    Write-Host "rcedit not found at $rcedit - attempting download"
    $url = 'https://github.com/electron/rcedit/releases/download/v1.1.1/rcedit-x64.exe'
    try {
        Invoke-WebRequest -Uri $url -OutFile $rcedit -ErrorAction Stop
    }
    catch {
        Write-Warning "Failed to download rcedit: $_"
    }
}

if ((Test-Path $rcedit) -and (Test-Path $distExe)) {
    # read metadata from release_meta.py
    $metaJson = & $python -c 'import json, release_meta; print(json.dumps({"ver":release_meta.VERSION,"author":release_meta.AUTHOR,"year":release_meta.YEAR,"url":release_meta.URL,"desc":release_meta.FILEDESC}))'
    $meta = $metaJson | ConvertFrom-Json
    $ver = "$($meta.ver).0"
    Write-Host "Applying version/resource strings to $distExe"
    & $rcedit $distExe --set-file-version $ver --set-product-version $ver --set-version-string "CompanyName" "$($meta.author)" --set-version-string "FileDescription" "$($meta.desc)" --set-version-string "LegalCopyright" "(c) $($meta.year) $($meta.author)" --set-version-string "OriginalFilename" "seamly2dk.exe" --set-version-string "ProductName" "seamly2dk" --set-version-string "Comments" "$($meta.url)"
    Write-Host "Applied resource strings."
}
else {
    Write-Warning "rcedit or built exe not found; skipping resource embedding."
}

Write-Host "Build finished. Check the 'dist' folder for seamly2dk.exe"