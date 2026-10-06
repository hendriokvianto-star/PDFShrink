# -*- mode: python ; coding: utf-8 -*-
#
# PDF Shrink — PyInstaller build specification
#
# Menghasilkan dua artefak:
#   1. PDFShrink.exe  (onefile)  — untuk distribusi umum
#   2. PDFShrink/     (onedir)   — untuk debugging & portable
#
# Cara build:
#   pip install pyinstaller
#   pyinstaller build.spec
#
# Output di: dist/PDFShrink.exe  dan  dist/PDFShrink/PDFShrink.exe
#
# Gate Check:
#   AC-11: Exe berjalan di Win10/11 tanpa Python terpasang
#   AC-12: Ukuran exe < 80 MB
#   AC-13: Berjalan dengan jaringan dinonaktifkan
#   AC-14: Berjalan dari folder non-admin (misal D:\portable\)

import sys
from pathlib import Path

block_cipher = None

# --- Paths ---
SRC_DIR = Path("src")

# ---------------------------------------------------------------------------
# Analysis — temukan semua modul dan dependensi
# ---------------------------------------------------------------------------
a = Analysis(
    # Entry point: pdfshrink/__main__.py dipanggil sebagai module
    [str(SRC_DIR / "pdfshrink" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        # CustomTkinter memerlukan folder assets-nya (themes, images)
        (
            str(
                Path(sys.executable).parent
                / "Lib"
                / "site-packages"
                / "customtkinter"
            ),
            "customtkinter",
        ),
    ],
    hiddenimports=[
        # pikepdf
        "pikepdf",
        "pikepdf._core",
        "pikepdf._cpphelpers",
        "pikepdf.models",
        "pikepdf.models.image",
        "pikepdf.objects",

        # Pillow image formats yang mungkin dibutuhkan
        "PIL",
        "PIL.Image",
        "PIL.ImageFile",
        "PIL.JpegImagePlugin",
        "PIL.JpegPresets",
        "PIL.PngImagePlugin",
        "PIL.TiffImagePlugin",
        "PIL.BmpImagePlugin",
        "PIL.GifImagePlugin",
        "PIL.WebPImagePlugin",

        # CustomTkinter
        "customtkinter",
        "customtkinter.windows",
        "customtkinter.windows.widgets",
        "customtkinter.windows.widgets.core_widget_classes",

        # Logging
        "logging.handlers",

        # tkinter (diperlukan CustomTkinter)
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.ttk",

        # Standard library
        "queue",
        "threading",
        "dataclasses",
        "pathlib",
        "json",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Eksklusi modul berat yang tidak digunakan
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "wx",
        "gi",
        "IPython",
        "jupyter",
        "notebook",
        "sphinx",
        "docutils",
        "setuptools",
        "pip",
        "pkg_resources",
        # Test dependencies
        "pytest",
        "reportlab",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# PYZ — archive bytecode Python
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE — onefile (distribusi utama)
# ---------------------------------------------------------------------------
exe_onefile = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PDFShrink",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,          # Gunakan UPX jika tersedia (memperkecil ukuran)
    upx_exclude=[
        "vcruntime140.dll",
        "python3*.dll",
        # pikepdf DLL — jangan compress, bisa rusak
        "_core*.pyd",
    ],
    runtime_tmpdir=None,
    console=False,      # --windowed: tidak ada console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon — tambahkan jika ada: icon="assets/icon.ico"
)

# ---------------------------------------------------------------------------
# COLLECT — onedir (portable / untuk debugging)
# ---------------------------------------------------------------------------
exe_onedir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFShrink",
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
)

coll = COLLECT(
    exe_onedir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "python3*.dll", "_core*.pyd"],
    name="PDFShrink",
)
