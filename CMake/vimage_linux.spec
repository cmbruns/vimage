# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ

block_cipher = None


a = Analysis(
    scripts=['../scripts/vimage.py'],
    pathex=["..", ],
    binaries=[
     ('/opt/libjpeg-turbo/lib64/libjpeg.so', '.'),
     ('/opt/libjpeg-turbo/lib64/libturbojpeg.so', '.'),
    ],
    datas=[
     ("../vmg/*.vert", "vmg"),
     ("../vmg/*.frag", "vmg"),
     ("../vmg/images/*", "vmg/images"),
     ("../vmg/git_hash.txt", "vmg"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='vimage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../vmg/images/cat_eye2.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='vimage'
)
