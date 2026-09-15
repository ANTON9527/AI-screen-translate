# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

# ---------- 定位关键目录 ----------
import paddle
paddle_lib_path = os.path.join(os.path.dirname(paddle.__file__), 'libs')

import paddleocr
paddleocr_path = os.path.dirname(paddleocr.__file__)
paddleocr_tools_path = os.path.join(paddleocr_path, 'tools')
paddleocr_ppocr_path = os.path.join(paddleocr_path, 'ppocr')


a = Analysis(
    ['src/17_app_region.py'],
    pathex=['D:\\AI screen translate'],
    binaries=[
        (paddle_lib_path, 'paddle/libs'),
    ],
    datas=[
        # --- paddleocr 的 tools 目录（双保险）---
        (paddleocr_tools_path, 'paddleocr/tools'),
        (paddleocr_tools_path, 'tools'),

        # --- paddleocr 的 ppocr 目录（含字符字典，双保险）---
        (paddleocr_ppocr_path, 'paddleocr/ppocr'),
        (paddleocr_ppocr_path, 'ppocr'),

        # --- 完整 paddleocr 目录 ---
        (paddleocr_path, 'paddleocr'),

        # --- 自动收集数据文件 ---
        *collect_data_files('paddleocr'),
        *collect_data_files('paddle'),
        *collect_data_files('pyclipper'),
        *collect_data_files('skimage'),
        *collect_data_files('imgaug'),
        *collect_data_files('scipy.io'),
        *collect_data_files('lmdb'),
        *collect_data_files('paddlex'),

        # --- 库的元数据 ---
        *copy_metadata('imageio'),
        *copy_metadata('imgaug'),
        *copy_metadata('scikit-image'),
        *copy_metadata('scipy'),
        *copy_metadata('numpy'),
        *copy_metadata('tqdm'),
        *copy_metadata('shapely'),
        *copy_metadata('paddleocr'),
        *copy_metadata('paddlepaddle'),
        *copy_metadata('opencv-python'),
        *copy_metadata('opencv-contrib-python'),
        *copy_metadata('pyclipper'),
        *copy_metadata('lmdb'),
        *copy_metadata('rapidfuzz'),
        *copy_metadata('pillow'),
        *copy_metadata('PyYAML'),
        *copy_metadata('requests'),
    ],
    hiddenimports=[
        'paddle',
        'paddleocr',
        'paddleocr.tools',
        'paddleocr.tools.infer',
        'paddleocr.ppocr',
        'ppocr',
        'pyclipper',
        'imghdr',
        'skimage',
        'imgaug',
        'imageio',
        'scipy.io',
        'lmdb',
        'paddlex',
        'pynput',
        'openai',
        'mss',
        'cv2',
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
    name='ScreenTranslator',
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