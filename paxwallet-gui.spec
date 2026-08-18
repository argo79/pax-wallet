# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('wallet_core.so', '.'), ('/home/argo/blobspace/retWallet2.0/venv/lib/python3.11/site-packages/xrpl/core/binarycodec/definitions/definitions.json', 'xrpl/core/binarycodec/definitions/'), ('reticulum', 'reticulum'), ('commands', 'commands'), ('utils', 'utils'), ('address_book.py', '.'), ('wallet_backend.py', '.'), ('ui', 'ui'), ('ui/resources', 'ui/resources')]
binaries = []
hiddenimports = ['bip32', 'mnemonic', 'xrpl', 'stellar_sdk', 'cryptography', 'ecdsa', 'base58', 'coincurve', 'wallet_manager', 'core_wrapper', 'colorama', 'RNS.Interfaces', 'RNS.Interfaces.Interface', 'PySocks', 'socks', 'httpx', 'socksio', 'address_book']
tmp_ret = collect_all('RNS')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['wallet_desktop.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='paxwallet-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
