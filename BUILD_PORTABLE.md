Building a portable Windows release (single-file .exe)

Overview

This project uses PyInstaller to build a single-file Windows executable. The repository includes helper scripts:

- `build_exe.ps1` — PowerShell script (preferred on Windows)
- `build_exe.bat` — Batch script for cmd.exe
- `release_meta.py` — metadata used by scripts to embed version/author via `rcedit`

Prerequisites

- Python installed (scripts expect `c:/python313/python.exe` by default). Edit the top of the script to match your Python path if different.
- Internet access to download PyInstaller and `rcedit` (scripts attempt to download `rcedit-x64.exe` into `build\seamly2dk\` if missing).

Quick build (PowerShell)

Open Developer PowerShell (or regular PowerShell) and run:

```powershell
cd /d G:\seamly2dk
.\build_exe.ps1
```

Quick build (Cmd)

```cmd
cd /d G:\seamly2dk
build_exe.bat
```

What the scripts do

1. Ensure `pip` is up-to-date and install `pyinstaller` into the configured Python interpreter.
2. Run PyInstaller:
   - `--onefile` — create a single executable
   - `--windowed` — hide console. Remove this flag to keep a console for debugging.
   - `--name seamly2dk` — output executable name
3. After PyInstaller finishes, the scripts look for `build\seamly2dk\rcedit-x64.exe` and attempt to download it if missing.
4. If `rcedit` and the built exe exist, they read `release_meta.py` and apply version / product strings to `dist\seamly2dk.exe`.

Where to edit metadata

Open `release_meta.py` and set:

- `VERSION` — semantic version (e.g. `'0.1.0'`)
- `AUTHOR` — author/company string
- `YEAR` — copyright year
- `URL` — project/release URL (used in Comments)
- `FILEDESC` — file description

The scripts will embed these strings into the generated executable using `rcedit`.

Notes & tips

- If your Python is in a virtualenv, either edit the script to point to that interpreter or activate the venv and run PyInstaller directly:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name seamly2dk main.py
```

- To debug problems with packaging, remove `--windowed` to see console output, or run PyInstaller without `--onefile` to inspect the bundled tree in `dist`/`build` folders.

- The scripts assume Windows DPI settings of 96 DPI when converting `px` units to mm (this only matters if embedding physical sizes).

- If `rcedit` download fails, fetch it manually from:
  https://github.com/electron/rcedit/releases
  and place `rcedit-x64.exe` into `build\seamly2dk\`.

Output

The resulting executable is `dist\seamly2dk.exe`. Test it on a clean Windows machine and ship any required sidecar files (e.g., saved JSON) as needed.

If you want, I can:
- run the build here (if the environment supports creating Windows exes), or
- create a Git commit adding this file and/or update `README_packaging.md` to reference it.