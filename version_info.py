# Version info for PyInstaller
# Edit the fields below before building to set executable metadata
VERSION = '0.0.1'
AUTHOR = 'D. Kibo'
YEAR = '2026'
URL = 'https://github.com/kibodmitry-yandex/seamly2dk/releases'

from PyInstaller.utils.win32.versioninfo import VSVersionInfo, StringStruct, StringTable, VarStruct, VarFileInfo, FixedFileInfo

filevers = tuple(int(x) for x in VERSION.split('.')) + (0,)
prodvers = filevers

vs = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=filevers,
        prodvers=prodvers,
        mask=0x3f,
        flags=0x0,
        OS=0x4,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringTable(
            u'040904B0',
            [
                StringStruct(u'CompanyName', AUTHOR),
                StringStruct(u'FileDescription', u'seamly2dk — OPD exporter (alpha)'),
                StringStruct(u'FileVersion', VERSION),
                StringStruct(u'InternalName', u'seamly2dk'),
                StringStruct(u'LegalCopyright', f'(c) {YEAR} {AUTHOR}'),
                StringStruct(u'OriginalFilename', u'seamly2dk.exe'),
                StringStruct(u'ProductName', u'seamly2dk'),
                StringStruct(u'ProductVersion', VERSION),
                StringStruct(u'Comments', URL),
            ]
        ),
        VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
    ]
)

# PyInstaller will import this file and look for a variable named `VSVersionInfo` or `vs`.
VSVersionInfo = vs
