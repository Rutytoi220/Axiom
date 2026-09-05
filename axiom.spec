# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# We need to manually include hidden imports that PyInstaller might miss,
# especially for ML dependencies and C-bindings.
hiddenimports = [
    # faster-whisper and its backend dependencies
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'av',
    
    # Desktop automation dependencies (often rely on dynamic loading)
    # Intentionally removed pyautogui and Xlib here to preserve lazy-loading
    # for graceful degradation on headless systems.
    
    # GUI
    'PySide6',
    
    # Core utilities
    'logging',
    'tempfile',
    'base64',
    'subprocess',
    'shutil',
    'pathlib',
    
    # New dependencies
    'markdown',
    'psutil',
    'packaging',
    'httpx',
    'aiofiles'
] + collect_submodules('tiktoken_ext')

# We need to bundle assets like images and fonts.
datas = [
    ('axiom/memory/schema.sql', 'axiom/memory'),
    ('axiom/gui/styles/*.qss*', 'axiom/gui/styles'),
    ('axiom/gui/styles/themes/*.json', 'axiom/gui/styles/themes'),
    ('axiom/gui/assets/fonts/*.ttf', 'axiom/gui/assets/fonts'),
] + collect_data_files('litellm') + collect_data_files('tiktoken')

# If there's an assets directory, let's include everything in it just in case
if os.path.exists('assets'):
    datas.append(('assets/*', 'assets/'))


a = Analysis(
    ['axiom/launcher.py'],
    pathex=[],
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
    name='AXIOM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    upx=True,
    upx_exclude=[],
    name='AXIOM',
)
