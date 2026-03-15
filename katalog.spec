# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec fajl za macOS .app bundle
Komanda za build:
    pyinstaller katalog.spec --noconfirm
"""

import sys
from pathlib import Path

block_cipher = None

# Detekcija PySide6 putanje (potrebno za Qt plugins)
try:
    import PySide6
    pyside6_dir = Path(PySide6.__file__).parent
except ImportError:
    pyside6_dir = None

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Uključi sve Python fajlove aplikacije
        ('app', 'app'),
        # Ikonica (PNG fallback ako ICNS ne postoji)
        ('assets/icon.png', 'assets'),
    ],
    hiddenimports=[
        # SQLAlchemy dialekti
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.pool',
        # Pandas/openpyxl/odf
        'pandas',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'odf',
        'odf.opendocument',
        # PySide6 moduli
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        # Python stdlib
        'logging.handlers',
        'decimal',
        'calendar',
        'unicodedata',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'numpy.distutils',
        'tkinter',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KataloškaProdaja',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,     # Bez konzolnog prozora na macOS
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='KataloškaProdaja',
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name='Kataloška prodaja.app',
    icon='assets/icon.icns',  # Generiše se sa: python scripts/make_icon.py
    bundle_identifier='com.katalog.prodaja',
    version='1.0.0',
    info_plist={
        'CFBundleName': 'Kataloška prodaja',
        'CFBundleDisplayName': 'Kataloška prodaja',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSMinimumSystemVersion': '11.0',
        'CFBundleDocumentTypes': [],
    },
)
