"""File list widget showing queued PDFs and compression results.

Scrollable list with filename, size, remove button, and post-compression
status updates. Maximum 20 files per batch.
Inline password prompt for encrypted PDFs (M5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk


MAX_FILES = 20


class FileRow(ctk.CTkFrame):
    """Single file row: name + size + remove button + status."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        file_path: Path,
        on_remove: Callable[[Path], None],
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", height=32, **kwargs)
        self.file_path = file_path
        self._on_remove = on_remove

        self.pack_propagate(False)

        size_kb = file_path.stat().st_size / 1024
        display_name = file_path.name
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."

        # Filename
        self._name_label = ctk.CTkLabel(
            self,
            text=f"• {display_name}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
            width=200,
        )
        self._name_label.pack(side="left", fill="x", expand=True)

        # Size
        self._size_label = ctk.CTkLabel(
            self,
            text=f"{size_kb:,.0f} KB",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="e",
            width=80,
        )
        self._size_label.pack(side="left", padx=(4, 4))

        # Status (shown after compression)
        self._status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="e",
            width=100,
        )
        self._status_label.pack(side="left", padx=(0, 4))

        # Remove button
        self._remove_btn = ctk.CTkButton(
            self,
            text="✕",
            width=28,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color=("gray85", "gray30"),
            text_color=("gray40", "gray60"),
            command=self._handle_remove,
        )
        self._remove_btn.pack(side="right")

    def _handle_remove(self) -> None:
        self._on_remove(self.file_path)

    def update_status(self, status: str, message: str) -> None:
        """Update the row after compression completes.

        Args:
            status: One of 'ok', 'below_min', 'failed', 'skipped'.
            message: Human-readable status message.
        """
        self._hide_password_prompt()
        color_map = {
            "ok": ("#2ecc71", "#2ecc71"),
            "below_min": ("#f39c12", "#f1c40f"),
            "failed": ("#e74c3c", "#e74c3c"),
            "skipped": ("#e74c3c", "#e74c3c"),
        }
        color = color_map.get(status, ("gray", "gray"))
        self._status_label.configure(text=message, text_color=color)
        self._remove_btn.configure(state="disabled")

    def disable_remove(self) -> None:
        """Disable the remove button during processing."""
        self._remove_btn.configure(state="disabled")

    def enable_remove(self) -> None:
        """Enable the remove button."""
        self._remove_btn.configure(state="normal")

    # ── Inline password prompt (M5) ──────────────────────────────

    def show_password_prompt(
        self, on_password: Callable[[Path, str], None],
    ) -> None:
        """Show an inline password entry for this file.

        The prompt is shown below the file row. When submitted,
        on_password is called with (file_path, password_text).
        An empty submit or Skip skips the file.

        Args:
            on_password: Callback receiving (path, password).
        """
        self._on_password = on_password
        self.configure(height=60)

        self._pw_frame = ctk.CTkFrame(self, fg_color="transparent", height=26)
        self._pw_frame.pack(fill="x", padx=4, pady=(2, 0))

        ctk.CTkLabel(
            self._pw_frame,
            text="🔒",
            font=ctk.CTkFont(size=11),
            width=20,
        ).pack(side="left")

        self._pw_entry = ctk.CTkEntry(
            self._pw_frame,
            width=140,
            height=24,
            placeholder_text="Sandi...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            show="●",
        )
        self._pw_entry.pack(side="left", padx=(2, 4))
        self._pw_entry.bind("<Return>", lambda _e: self._submit_password())

        self._pw_submit_btn = ctk.CTkButton(
            self._pw_frame,
            text="OK",
            width=32,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self._submit_password,
        )
        self._pw_submit_btn.pack(side="left", padx=(0, 4))

        self._pw_skip_btn = ctk.CTkButton(
            self._pw_frame,
            text="Lewati",
            width=50,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="transparent",
            hover_color=("gray85", "gray30"),
            text_color=("gray40", "gray60"),
            command=self._skip_password,
        )
        self._pw_skip_btn.pack(side="left")

        self._status_label.configure(
            text="terkunci", text_color=("#e67e22", "#f39c12")
        )
        self._pw_entry.focus_set()

    def _submit_password(self) -> None:
        """User submitted a password."""
        pw = self._pw_entry.get().strip()
        self._hide_password_prompt()
        if self._on_password:
            self._on_password(self.file_path, pw if pw else "")

    def _skip_password(self) -> None:
        """User chose to skip this encrypted file."""
        self._hide_password_prompt()
        if self._on_password:
            self._on_password(self.file_path, "")

    def _hide_password_prompt(self) -> None:
        """Remove the password prompt if visible."""
        if hasattr(self, "_pw_frame") and self._pw_frame.winfo_exists():
            self._pw_frame.destroy()
            self.configure(height=32)


class FileList(ctk.CTkFrame):
    """Scrollable file list with add/remove/status functionality.

    Attributes:
        files: List of currently loaded file paths.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_files_change: Callable[[int], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_files_change = on_files_change
        self._rows: dict[Path, FileRow] = {}

        # Header
        header = ctk.CTkLabel(
            self,
            text=f"Daftar file (maks. {MAX_FILES}):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 4))

        # Scrollable container
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            height=100,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
        )
        self._scroll_frame.pack(fill="x")

        # Empty state label
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="Belum ada file ditambahkan.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "gray60"),
        )
        self._empty_label.pack(pady=10)

        # Message label (for inline errors)
        self._message_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#e74c3c",
            anchor="w",
        )
        self._message_label.pack(fill="x", pady=(2, 0))

    @property
    def files(self) -> list[Path]:
        return list(self._rows.keys())

    @property
    def file_count(self) -> int:
        return len(self._rows)

    def add_files(self, paths: list[Path]) -> None:
        """Add files to the list, rejecting non-PDFs and duplicates.

        Args:
            paths: List of file paths to add.
        """
        self._message_label.configure(text="")
        rejected = []

        for path in paths:
            if self.file_count >= MAX_FILES:
                self._message_label.configure(
                    text=f"Maks. {MAX_FILES} file per batch."
                )
                break

            if path in self._rows:
                continue  # Skip duplicates silently

            if not path.suffix.lower() == ".pdf":
                rejected.append(path.name)
                continue

            if not path.exists():
                rejected.append(path.name)
                continue

            # Add row
            row = FileRow(
                self._scroll_frame,
                file_path=path,
                on_remove=self._remove_file,
            )
            row.pack(fill="x", padx=4, pady=1)
            self._rows[path] = row

        if rejected:
            names = ", ".join(rejected[:3])
            self._message_label.configure(
                text=f"Ditolak (bukan PDF): {names}"
            )

        self._update_empty_state()
        if self._on_files_change:
            self._on_files_change(self.file_count)

    def _remove_file(self, path: Path) -> None:
        """Remove a file from the list."""
        if path in self._rows:
            self._rows[path].destroy()
            del self._rows[path]
            self._update_empty_state()
            if self._on_files_change:
                self._on_files_change(self.file_count)

    def _update_empty_state(self) -> None:
        """Show/hide the empty state label."""
        if self.file_count == 0:
            self._empty_label.pack(pady=10)
        else:
            self._empty_label.pack_forget()

    def update_file_status(self, path: Path, status: str, message: str) -> None:
        """Update the status of a specific file after compression.

        Args:
            path: The file path to update.
            status: One of 'ok', 'below_min', 'failed', 'skipped'.
            message: Human-readable status message.
        """
        if path in self._rows:
            self._rows[path].update_status(status, message)

    def disable_all_remove(self) -> None:
        """Disable all remove buttons (during processing)."""
        for row in self._rows.values():
            row.disable_remove()

    def enable_all_remove(self) -> None:
        """Enable all remove buttons (after processing)."""
        for row in self._rows.values():
            row.enable_remove()

    def clear_all(self) -> None:
        """Remove all files from the list."""
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()
        self._update_empty_state()
        if self._on_files_change:
            self._on_files_change(0)

    def show_password_prompt(
        self, path: Path, on_password: Callable[[Path, str], None],
    ) -> None:
        """Show inline password prompt for an encrypted file.

        Args:
            path: File path that needs a password.
            on_password: Callback with (path, password). Empty string = skip.
        """
        if path in self._rows:
            self._rows[path].show_password_prompt(on_password)
