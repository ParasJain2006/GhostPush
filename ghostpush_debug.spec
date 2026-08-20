# -*- mode: python ; coding: utf-8 -*-

"""DEBUG PyInstaller Specification for GhostPush.

Identical to ghostpush.spec except:
- console=True  (shows stdout/stderr traceback in terminal)
- name='GhostPushDebug'
- output collected to dist/GhostPushDebug
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Analysis configuration
datas = [
    ('extension', 'extension'),
    ('.env.example', '.'),
]

hiddenimports = [
    # Uvicorn & ASGI runtime modules
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    # System Tray & UI
    'pystray._win32',
    'PIL._imaging',
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    # Web framework & validation
    'fastapi',
    'starlette',
    'pydantic',
    'dotenv',
    # Shared contracts & backend modules
    'common',
    'common.constants',
    'common.enums',
    'common.errors',
    'common.schemas',
    'backend',
    'backend.agent.adapter',
    'backend.api.app',
    'backend.api.routes.config',
    'backend.api.routes.health',
    'backend.api.routes.jobs',
    'backend.api.websocket',
    'backend.config.manager',
    'backend.config.models',
    'backend.config.settings',
    'backend.db.database',
    'backend.db.repository',
    'backend.db.schema',
    'backend.jobs.queue',
    'backend.jobs.worker',
    # Paras Agent & MCP modules
    'agent',
    'agent.graph',
    'agent.prompts',
    'agent.providers',
    'agent.runner',
    'mcp',
    'mcp.file_tool',
    'mcp.git_tool',
    'mcp.notification_tool',
]

a = Analysis(
    ['scripts/launch.py'],
    pathex=['.'],
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
    name='GhostPushDebug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # <-- console window enabled for traceback capture
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ghostpush.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GhostPushDebug',
)
