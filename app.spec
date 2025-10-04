# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for RDO Map Overlay backend.
Builds a standalone executable with all dependencies bundled.
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Map downloaded on first launch to reduce installer size
        # ('data/rdr2_map_hq.png', 'data'),
        ('config/*.py', 'config'),
    ],
    hiddenimports=[
        'cv2',
        'flask',
        'flask_socketio',
        'flask_cors',
        'socketio',
        'engineio',
        'engineio.async_drivers.threading',
        'numpy',
        'PIL',
        'requests',
        'mss',
        'win32gui',
        'win32con',
        'windows_capture',
        'core.port_manager',
        'core.map_downloader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy packages we don't use
        'matplotlib',
        'tkinter',
        'IPython',
        'notebook',
        'jupyter',
        'pandas',
        'scipy',
        'sympy',
        'pytest',
        'setuptools',
        'distutils',
        # Test frameworks
        'unittest',
        '_pytest',
        # Documentation
        'sphinx',
        'docutils',
        # Unused OpenCV modules
        'cv2.aruco',
        'cv2.bgsegm',
        'cv2.face',
        'cv2.dnn_superres',
        'cv2.ximgproc',
        'cv2.xfeatures2d',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='rdo-overlay-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - critical for user experience
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add backend icon
)
