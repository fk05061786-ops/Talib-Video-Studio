# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Talib Video Studio (Windows GUI executable).

Entry point: src/main.py. Bundles PySide6, all ``src`` packages, the Qt
stylesheet and ``.env.hub``. If optional ``bin/ffmpeg.exe`` /
``bin/ffprobe.exe`` files exist they are bundled under ``bin/`` and take
precedence over PATH at runtime.
"""

from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / ".env.hub"), "."),
    (str(ROOT / "src" / "ui" / "theme.qss"), "src/ui"),
]
for _binary in ("ffmpeg.exe", "ffprobe.exe", "ffmpeg", "ffprobe"):
    _path = ROOT / "bin" / _binary
    if _path.is_file():
        datas.append((str(_path), "bin"))

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork",
    "src",
    "src.app",
    "src.app.project",
    "src.app.session",
    "src.core",
    "src.core.audio",
    "src.core.export",
    "src.core.export_validation",
    "src.core.media",
    "src.core.text_styles",
    "src.core.timecode",
    "src.core.timeline",
    "src.core.timeline_ops",
    "src.core.transitions",
    "src.ui",
    "src.ui.dialogs",
    "src.ui.main_window",
    "src.ui.player",
    "src.ui.panels",
    "src.ui.panels.base_panel",
    "src.ui.panels.export_panel",
    "src.ui.panels.media_bin",
    "src.ui.panels.monitor",
    "src.ui.panels.timeline",
    "src.utils",
    "src.utils.ffmpeg",
    "src.utils.packaging",
]

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="TalibVideoStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TalibVideoStudio",
)
