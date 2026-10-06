"""Main application window for PDF Shrink.

CustomTkinter-based GUI. Connects the drop zone, file list, size inputs,
and progress display to the core compression engine via threading.

Window: 520×560 px, non-resizable, title "PDF Shrink".
Theme: System mode, blue accent, Segoe UI font.
Threading: daemon worker thread + queue.Queue + root.after(100, poll).
Password prompts handled inline via cross-thread Event synchronization.
"""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from pdfshrink.config import (
    AppConfig, load_config, save_config, setup_logging, install_crash_handler,
)
from pdfshrink.core.compressor import compress_one
from pdfshrink.core.models import Job, Result, Settings
from pdfshrink.errors import PasswordRequired
from pdfshrink.widgets.drop_zone import DropZone
from pdfshrink.widgets.file_list import FileList
from pdfshrink.widgets.size_inputs import SizeInputs


# Default output folder
_DEFAULT_OUTPUT = Path.home() / "Documents" / "PDF Shrink"


class PDFShrinkApp(ctk.CTk):
    """Main application window for PDF Shrink."""

    def __init__(self) -> None:
        super().__init__()

        # Load persisted config (M6)
        self._config = load_config()

        # Window properties
        self.title("PDF Shrink")
        self.geometry("520x640")
        self.resizable(False, False)

        # Appearance — use persisted preference
        ctk.set_appearance_mode(self._config.appearance)
        ctk.set_default_color_theme("blue")

        # State — restore from config
        self._output_dir = Path(self._config.output_dir)
        self._is_compressing = False
        self._cancel_event = threading.Event()
        self._result_queue: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None

        # Password prompt synchronization (M5)
        self._pw_event = threading.Event()
        self._pw_responses: dict[Path, str] = {}

        # Build UI
        self._build_ui()

        # Apply persisted min/max KB values
        self._size_inputs.min_var.set(str(self._config.last_min_kb))
        self._size_inputs.max_var.set(str(self._config.last_max_kb))

        # Initial button state
        self._update_compress_button_state()

        # Save config on window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Construct all UI components."""
        # Main container with padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=10)

        # --- Title ---
        title = ctk.CTkLabel(
            container,
            text="PDF Shrink",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 6))

        # --- Drop Zone ---
        self._drop_zone = DropZone(
            container,
            on_files_dropped=self._on_files_added,
        )
        self._drop_zone.pack(fill="x", pady=(0, 6))

        # --- File List ---
        self._file_list = FileList(
            container,
            on_files_change=self._on_file_count_changed,
        )
        self._file_list.pack(fill="x", pady=(0, 6))

        # --- Size Inputs ---
        self._size_inputs = SizeInputs(
            container,
            on_validation_change=self._on_validation_changed,
        )
        self._size_inputs.pack(fill="x", pady=(0, 6))

        # --- Output Folder ---
        folder_frame = ctk.CTkFrame(container, fg_color="transparent")
        folder_frame.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            folder_frame,
            text="Folder hasil:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        ).pack(side="left")

        self._folder_label = ctk.CTkLabel(
            folder_frame,
            text=str(self._output_dir),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray60"),
            anchor="w",
        )
        self._folder_label.pack(side="left", fill="x", expand=True, padx=(6, 6))

        self._change_folder_btn = ctk.CTkButton(
            folder_frame,
            text="Ubah",
            width=60,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._change_output_folder,
        )
        self._change_folder_btn.pack(side="right")

        # --- Progress ---
        self._progress_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._progress_frame.pack(fill="x", pady=(0, 6))

        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame, height=14,
        )
        self._progress_bar.pack(fill="x", pady=(0, 4))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(
            self._progress_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray60"),
            anchor="w",
        )
        self._progress_label.pack(fill="x")

        # --- Action Buttons ---
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 0))

        self._compress_btn = ctk.CTkButton(
            btn_frame,
            text="Kompres",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._on_compress_click,
        )
        self._compress_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._open_folder_btn = ctk.CTkButton(
            btn_frame,
            text="Buka Folder",
            height=38,
            width=120,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._open_output_folder,
        )
        self._open_folder_btn.pack(side="right")

    # ── Event Handlers ───────────────────────────────────────────────

    def _on_files_added(self, paths: list[Path]) -> None:
        """Handle files added from drop zone or file dialog."""
        self._file_list.add_files(paths)

    def _on_file_count_changed(self, count: int) -> None:
        """Handle file count change in the file list."""
        self._update_compress_button_state()

    def _on_validation_changed(self, is_valid: bool) -> None:
        """Handle size input validation change."""
        self._update_compress_button_state()

    def _update_compress_button_state(self) -> None:
        """Enable/disable compress button based on state."""
        can_compress = (
            self._file_list.file_count > 0
            and self._size_inputs.is_valid
            and not self._is_compressing
        )
        self._compress_btn.configure(
            state="normal" if can_compress else "disabled"
        )

    def _change_output_folder(self) -> None:
        """Open folder picker to change output directory."""
        folder = filedialog.askdirectory(
            title="Pilih Folder Hasil",
            initialdir=str(self._output_dir),
        )
        if folder:
            self._output_dir = Path(folder)
            # Truncate display for long paths
            display = str(self._output_dir)
            if len(display) > 45:
                display = "..." + display[-42:]
            self._folder_label.configure(text=display)
            # Persist folder change (M6)
            self._save_current_config()

    def _open_output_folder(self) -> None:
        """Open the output folder in Windows Explorer."""
        if self._output_dir.exists():
            os.startfile(str(self._output_dir))
        else:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self._output_dir))

    # ── Compression ──────────────────────────────────────────────────

    def _on_compress_click(self) -> None:
        """Handle compress/cancel button click."""
        if self._is_compressing:
            # Cancel
            self._cancel_event.set()
            self._compress_btn.configure(text="Membatalkan...", state="disabled")
            return

        # Start compression
        self._start_compression()

    def _start_compression(self) -> None:
        """Start the compression process in a worker thread."""
        files = self._file_list.files
        if not files:
            return

        settings = Settings(
            min_kb=self._size_inputs.get_min_kb(),
            max_kb=self._size_inputs.get_max_kb(),
            output_dir=self._output_dir,
        )

        jobs = [
            Job(src=f, original_bytes=f.stat().st_size)
            for f in files
        ]

        # UI state: compressing
        self._is_compressing = True
        self._cancel_event.clear()
        self._compress_btn.configure(text="Batalkan")
        self._drop_zone.set_enabled(False)
        self._file_list.disable_all_remove()
        self._change_folder_btn.configure(state="disabled")
        self._progress_bar.set(0)
        self._progress_label.configure(text="Memulai kompresi...")

        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_run,
            args=(jobs, settings),
            daemon=True,
        )
        self._worker_thread.start()

        # Start polling
        self.after(100, self._poll_results)

    def _worker_run(self, jobs: list[Job], settings: Settings) -> None:
        """Worker thread: compress files one by one with error isolation.

        Each file is processed independently. If PasswordRequired is raised,
        the worker pauses and asks the GUI for a password via queue+Event.
        One file's failure never stops the batch (AC-4).
        """
        results: list[Result] = []
        total = len(jobs)

        for idx, job in enumerate(jobs):
            if self._cancel_event.is_set():
                # Mark remaining as cancelled
                for remaining in jobs[idx:]:
                    r = Result(
                        job=remaining, status="skipped", output=None,
                        final_bytes=None, attempts=0,
                        message="✖ dibatalkan",
                    )
                    results.append(r)
                    self._result_queue.put(("file_done", r))
                break

            self._result_queue.put(("progress", idx, total))

            try:
                r = self._compress_with_password_retry(job, settings)
            except Exception as e:
                r = Result(
                    job=job, status="skipped", output=None,
                    final_bytes=None, attempts=0,
                    message=f"✖ error: {e}",
                )

            results.append(r)
            self._result_queue.put(("file_done", r))

        self._result_queue.put(("progress", total, total))
        self._result_queue.put(("batch_done", results))

    def _compress_with_password_retry(
        self, job: Job, settings: Settings,
    ) -> Result:
        """Attempt compression, prompting for password if needed.

        Pre-checks if the PDF is encrypted via pikepdf. If so, asks
        the GUI for a password before calling compress_one. This avoids
        the issue of compress_one catching PasswordRequired internally.
        """
        # Pre-check: is the file encrypted?
        if job.password is None:
            from pdfshrink.core.pdfio import open_pdf
            try:
                pdf = open_pdf(job.src)
                pdf.close()
            except PasswordRequired:
                # File is encrypted — ask GUI for password
                self._pw_event.clear()
                self._result_queue.put(("password_needed", job.src))

                # Wait for GUI response (blocks worker, not GUI)
                while not self._pw_event.is_set():
                    if self._cancel_event.is_set():
                        return Result(
                            job=job, status="skipped", output=None,
                            final_bytes=None, attempts=0,
                            message="✖ dibatalkan",
                        )
                    self._pw_event.wait(timeout=0.2)

                password = self._pw_responses.pop(job.src, "")
                if not password:
                    return Result(
                        job=job, status="skipped", output=None,
                        final_bytes=None, attempts=0,
                        message="✖ terkunci sandi",
                    )

                # Retry with password
                job = Job(
                    src=job.src,
                    original_bytes=job.original_bytes,
                    password=password,
                )
            except Exception:
                pass  # Let compress_one handle other errors

        # Run compression (with or without password)
        return compress_one(
            job, settings,
            on_progress=lambda frac: None,
            cancel=self._cancel_event,
        )

    def _poll_results(self) -> None:
        """Poll the result queue for updates from worker thread."""
        try:
            while True:
                msg = self._result_queue.get_nowait()

                if msg[0] == "progress":
                    _, current, total = msg
                    if total > 0:
                        frac = min(current, total) / total
                        self._progress_bar.set(frac)
                        if current < total:
                            self._progress_label.configure(
                                text=f"Memproses {current + 1} dari {total}..."
                            )

                elif msg[0] == "file_done":
                    result: Result = msg[1]
                    self._file_list.update_file_status(
                        result.job.src, result.status, result.message
                    )

                elif msg[0] == "password_needed":
                    file_path: Path = msg[1]
                    self._file_list.show_password_prompt(
                        file_path, self._on_password_submitted
                    )

                elif msg[0] == "batch_done":
                    results: list[Result] = msg[1]
                    self._on_compression_complete(results)
                    return  # Stop polling

                elif msg[0] == "error":
                    self._progress_label.configure(
                        text=f"Error: {msg[1]}"
                    )
                    self._on_compression_complete([])
                    return

        except queue.Empty:
            pass

        # Continue polling if still compressing
        if self._is_compressing:
            self.after(100, self._poll_results)

    def _on_password_submitted(self, path: Path, password: str) -> None:
        """Handle password submission from the inline prompt.

        Stores the password and signals the worker thread to resume.
        """
        self._pw_responses[path] = password
        self._pw_event.set()

    def _on_compression_complete(self, results: list[Result]) -> None:
        """Handle compression batch completion."""
        self._is_compressing = False
        self._worker_thread = None

        # Summary
        ok_count = sum(1 for r in results if r.status in ("ok", "below_min"))
        fail_count = sum(1 for r in results if r.status == "failed")
        skip_count = sum(1 for r in results if r.status == "skipped")

        if self._cancel_event.is_set():
            summary = "Kompresi dibatalkan."
        else:
            summary = f"Selesai: {ok_count} berhasil"
            if fail_count:
                summary += f", {fail_count} gagal"
            if skip_count:
                summary += f", {skip_count} dilewati"

        self._progress_bar.set(1.0 if not self._cancel_event.is_set() else 0)
        self._progress_label.configure(text=summary)

        # Restore UI
        self._compress_btn.configure(text="Kompres")
        self._drop_zone.set_enabled(True)
        self._change_folder_btn.configure(state="normal")
        self._update_compress_button_state()

        # Persist last-used settings (M6)
        self._save_current_config()

    def _save_current_config(self) -> None:
        """Persist current settings to config.json."""
        self._config.output_dir = str(self._output_dir)
        self._config.last_min_kb = self._size_inputs.get_min_kb()
        self._config.last_max_kb = self._size_inputs.get_max_kb()
        save_config(self._config)

    def _on_close(self) -> None:
        """Handle window close: save config, then destroy."""
        self._save_current_config()
        self.destroy()


def run_app() -> None:
    """Launch the PDF Shrink application.

    Sets up logging and crash handler before creating the window.
    """
    setup_logging()
    install_crash_handler()
    app = PDFShrinkApp()
    app.mainloop()
