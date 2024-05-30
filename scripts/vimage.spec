# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../scripts/vimage.py'],
    pathex=[],
    binaries=[],
    datas=[
        ("../vmg/*.vert", "vmg"),
        ("../vmg/*.frag", "vmg"),
        ("../vmg/images/*", "vmg/images"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../vmg/images/cat_eye2.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='vimage',
)
app = BUNDLE(
    coll,
    name="vimage.app",
    icon="../vmg/images/cat_eye2.ico",
    bundle_identifier=None,
    info_plist={
    	"CFBundleDisplayName": "vimage",
	    "CFBundleExecutable": "vimage",
	    "CFBundleIdentifier": "vimage",
	    "CFBundleInfoDictionaryVersion": "6.0",
	    "CFBundleName": "vimage",
	    "CFBundlePackageType": "APPL",
	    "CFBundleShortVersionString": "0.0.0",
	    "NSHighResolutionCapable": True,
	    'CFBundleDocumentTypes': [
	        {
                'CFBundleTypeName': 'GIF Image',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['com.compuserve.gif'],
                'LSHandlerRank': 'Owner'
            },
            {
                'CFBundleTypeName': 'public.jpeg',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['public.jpeg'],
                'LSHandlerRank': 'Owner'
            },
            {
                'CFBundleTypeName': 'public.png',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['public.png'],
                'LSHandlerRank': 'Owner'
            },
        ]
    }
)
