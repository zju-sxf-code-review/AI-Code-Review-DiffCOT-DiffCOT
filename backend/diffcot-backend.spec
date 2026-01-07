# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件
用于将 DiffCOT 后端打包为独立可执行文件
"""

import os
import sys
from pathlib import Path

# 获取项目根目录 (PyInstaller spec 文件中使用 SPECPATH)
ROOT_DIR = Path(SPECPATH).absolute()

# 分析主入口
a = Analysis(
    ['main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        # 包含配置文件
        ('configs/semgrep_rules', 'configs/semgrep_rules'),
        ('configs/*.py', 'configs'),
    ],
    hiddenimports=[
        # FastAPI 相关
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Pydantic
        'pydantic',
        'pydantic.fields',
        # 项目模块
        'api',
        'api.routes',
        'api.routes.review',
        'api.routes.conversations',
        'api.routes.github',
        'api.routes.settings',
        'api.routes.semgrep_rules',
        'api.models',
        'api.models.schemas',
        'api.database',
        'api.config_manager',
        'client',
        'client.github_client',
        'client.claude_api_client',
        'client.glm_api_client',
        'client.semgrep_client',
        'client.context_extractor',
        'client.symbol_extractor',
        'review_engine',
        'review_engine.review_workflow',
        'configs',
        'configs.review_rules',
        'configs.pr_size_limits',
        'configs.constants',
        'utils',
        'utils.logger',
        'utils.json_parser',
        'utils.paths',
        # LangGraph
        'langgraph',
        'langchain_core',
        # 其他
        'yaml',
        'httpx',
        'anthropic',
        'openai',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI 相关
        'tkinter',
        'matplotlib',
        'PIL',
        'Pillow',

        # 数据科学（不需要）
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'scikit-learn',

        # 深度学习（不需要）
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'onnxruntime',
        'onnx',

        # 计算机视觉（不需要）
        'cv2',
        'opencv-python',
        'opencv-contrib-python',

        # 大数据/云服务（不需要）
        'pyarrow',
        'arrow',
        'botocore',
        'boto3',
        'awscli',
        's3transfer',

        # PDF 处理（不需要）
        'pymupdf',
        'fitz',
        'pikepdf',
        'pdfminer',
        'pypdfium2',

        # 编译器/JIT（不需要）
        'llvmlite',
        'numba',

        # NLP（不需要）
        'nltk',
        'jieba',
        'spacy',

        # 其他大型库
        'grpc',
        'grpcio',
        'h5py',
        'lxml',

        # 测试相关
        'pytest',
        'pytest_asyncio',
        '_pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='diffcot-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保持控制台输出便于调试
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
    name='diffcot-backend',
)
