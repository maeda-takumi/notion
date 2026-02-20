# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
login_icon_path = 'img/L_icon.ico'


a = Analysis(
    ['notion_login_manager.py'],
    pathex=[],
    binaries=[],
    datas=[(login_icon_path, 'img')],
    hiddenimports=[
        "selenium.webdriver.chrome.webdriver",
        "selenium.webdriver.chrome.service",
        "selenium.webdriver.common.by",
        "selenium.webdriver.support.ui",
        "selenium.webdriver.support.expected_conditions",
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='notion_login_manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=login_icon_path,
)