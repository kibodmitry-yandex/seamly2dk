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
	`release_meta.py` to set `VERSION`, `AUTHOR`, `YEAR`, `URL`, and `FILEDESC` used by the post-build step.
	The build scripts now perform the sequence: build with PyInstaller (no version-file), then run `rcedit` to embed
	string metadata into the generated `dist\seamly2dk.exe`. This avoids PyInstaller parsing issues with text version files.
	Edit `release_meta.py` before running the build to change metadata.

If you'd like, I can run the build here and upload the resulting exe (if environment permits).