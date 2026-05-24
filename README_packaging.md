Packaging (Windows .exe)

This project is a Tkinter-based Python app. To produce a single-file Windows executable use PyInstaller.

Prerequisites:
- Python 3.13 installed and accessible at `c:/python313/python.exe` (adjust scripts if different).
- Internet access to install PyInstaller.

Quick build (PowerShell):

```powershell
cd i:\seamly2dk
.\build_exe.ps1
```

Quick build (Cmd):

```cmd
cd /d i:\seamly2dk
build_exe.bat
```

Notes:
- The produced executable will be in `dist\seamly2dk.exe`.
- The app uses relative file access; distribute sidecar `.json` files alongside the exe as needed.
- For debugging, remove `--windowed` from the PyInstaller command to keep a console.
 - To embed Windows file metadata (author, version, copyright, download URL), edit
	 `version_info.py` at the repo root and then run the same build scripts. PyInstaller
	 will embed those fields into the generated `.exe` using the `--version-file` option.
	 The following fields are available at the top of `version_info.py`:
	 - `VERSION` (e.g. `0.1.0`)
	 - `AUTHOR` (company/author name)
	 - `YEAR` (copyright year)
	 - `URL` (download/updates page — stored in `Comments`)

If you'd like, I can run the build here and upload the resulting exe (if environment permits).