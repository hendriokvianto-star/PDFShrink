"""CLI entry point for PDF Shrink core compression.

Usage:
    python -m pdfshrink --in file.pdf --max 300
    python -m pdfshrink --in file.pdf --min 100 --max 300
    python -m pdfshrink --in file.pdf --max 500 --out ./output
    python -m pdfshrink --in file1.pdf file2.pdf --max 300

For GUI mode (when implemented):
    python -m pdfshrink --gui
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

# True ketika berjalan sebagai onefile/onedir exe PyInstaller
_IS_FROZEN = getattr(sys, 'frozen', False)

from pdfshrink.core.compressor import compress_batch
from pdfshrink.core.models import Job, Result, Settings


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdfshrink",
        description="PDF Shrink — Kompresi PDF offline ke rentang ukuran target.",
    )
    parser.add_argument(
        "--in", "-i",
        dest="input_files",
        nargs="+",
        type=Path,
        help="Satu atau lebih file PDF untuk dikompresi.",
    )
    parser.add_argument(
        "--min",
        type=int,
        default=0,
        help="Ukuran minimum target dalam KB (default: 0, tanpa batas bawah).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Ukuran maksimum target dalam KB.",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        default=None,
        help="Folder output (default: folder yang sama dengan file sumber).",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Jalankan dalam mode GUI (memerlukan CustomTkinter).",
    )

    return parser.parse_args(argv)


def _on_file_done(result: Result) -> None:
    """Print result for each completed file."""
    src_name = result.job.src.name
    status_icon = {
        "ok": "✔",
        "below_min": "✔",
        "failed": "✖",
        "skipped": "✖",
    }
    icon = status_icon.get(result.status, "?")
    print(f"  {icon} {src_name}: {result.message}")


def _on_progress(current: int, total: int) -> None:
    """Print overall batch progress."""
    if total > 0:
        print(f"\rMemproses {current + 1} dari {total}...", end="", flush=True)


def _show_error_dialog(title: str, message: str) -> None:
    """Tampilkan MessageBox Windows untuk error di windowed mode."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass  # Jika gagal, diam saja


def main(argv: list[str] | None = None) -> int:
    """CLI main function.

    Jika dijalankan tanpa argumen (mis. double-click exe), otomatis
    membuka GUI. Jika ada argumen --in / --max, jalankan mode CLI.

    Returns:
        Exit code: 0 if all succeeded, 1 if any failed.
    """
    args = _parse_args(argv)

    # GUI mode: --gui flag ATAU double-click tanpa argumen
    if args.gui or (not args.input_files and args.max is None):
        try:
            from pdfshrink.app import run_app
            run_app()
        except Exception as e:
            import traceback
            detail = traceback.format_exc()
            _show_error_dialog(
                "PDF Shrink — Error",
                f"Gagal membuka aplikasi:\n{e}\n\nDetail:\n{detail[:500]}",
            )
            return 1
        return 0

    # Validate inputs (required in CLI mode)
    if not args.input_files:
        print("✖ --in diperlukan. Gunakan --gui untuk mode GUI.", file=sys.stderr)
        return 1
    if args.max is None:
        print("✖ --max diperlukan. Gunakan --gui untuk mode GUI.", file=sys.stderr)
        return 1

    input_files: list[Path] = args.input_files
    for f in input_files:
        if not f.exists():
            print(f"✖ File tidak ditemukan: {f}", file=sys.stderr)
            return 1
        if not f.suffix.lower() == ".pdf":
            print(f"✖ Bukan file PDF: {f}", file=sys.stderr)
            return 1

    # Determine output directory
    if args.out:
        output_dir = args.out
    else:
        # Default: same directory as first input file
        output_dir = input_files[0].parent / "PDF Shrink Output"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate min/max
    if args.max <= 0:
        print("✖ --max harus > 0", file=sys.stderr)
        return 1
    if args.max <= args.min:
        print("✖ --max harus > --min", file=sys.stderr)
        return 1

    # Build jobs
    settings = Settings(
        min_kb=args.min,
        max_kb=args.max,
        output_dir=output_dir,
    )

    jobs = [
        Job(src=f, original_bytes=f.stat().st_size)
        for f in input_files
    ]

    cancel = threading.Event()

    print(f"PDF Shrink v1.0.0")
    print(f"Target: {settings.min_kb}–{settings.max_kb} KB")
    print(f"Output: {output_dir}")
    print(f"File: {len(jobs)} file(s)")
    print()

    # Run compression
    results = compress_batch(
        jobs=jobs,
        settings=settings,
        on_file_done=_on_file_done,
        on_progress=_on_progress,
        cancel=cancel,
    )

    print()  # Newline after progress
    print()

    # Summary
    ok_count = sum(1 for r in results if r.status in ("ok", "below_min"))
    fail_count = sum(1 for r in results if r.status == "failed")
    skip_count = sum(1 for r in results if r.status == "skipped")

    print(f"Selesai: {ok_count} berhasil, {fail_count} gagal, {skip_count} dilewati")

    if ok_count > 0:
        print(f"Hasil tersimpan di: {output_dir}")

    return 0 if fail_count == 0 and skip_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
