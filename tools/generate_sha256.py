import hashlib
from pathlib import Path

exe = Path('dist') / 'seamly2dk.exe'
out = Path('dist') / 'seamly2dk.exe.sha256'

if not exe.exists():
    print('MISSING', exe)
    raise SystemExit(2)

h = hashlib.sha256()
with exe.open('rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        h.update(chunk)

line = f"{h.hexdigest()}  {exe.name}\n"
out.write_text(line, encoding='ascii')
print('WROTE', out)
print(line.strip())
