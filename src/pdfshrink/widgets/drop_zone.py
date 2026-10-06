"""Drop zone widget for drag-and-drop PDF file input.

Provides a visual area with a "Pilih File" button for selecting PDFs.
Drag-and-drop support via tkinterdnd2 if available, otherwise
button-only mode (documented in LIMITATIONS.md).
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk


class DropZone(ctk.CTkFrame):
    """Drop zone area with file selection button.

    If tkinterdnd2 is available, also supports drag-and-drop.
    Otherwise, only the "Pilih File" button is available.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_files_dropped: Callable[[list[Path]], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            height=80,
            corner_radius=8,
            border_width=2,
            border_color=("gray70", "gray40"),
            fg_color=("gray92", "gray17"),
            **kwargs,
        )
        self._on_files_dropped = on_files_dropped
        self._dnd_available = False

        self.pack_propagate(False)

        # Inner content frame
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Icon/text label
        self._label = ctk.CTkLabel(
            inner,
            text="📄 Tarik file PDF ke sini",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("gray40", "gray60"),
        )
        self._label.pack(pady=(0, 8))

        # "atau" label
        ctk.CTkLabel(
            inner,
            text="atau",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "gray60"),
        ).pack(pady=(0, 6))

        # File picker button
        self._pick_btn = ctk.CTkButton(
            inner,
            text="Pilih File",
            width=120,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._open_file_dialog,
        )
        self._pick_btn.pack()

        # Try to enable drag-and-drop via tkinterdnd2
        self._try_enable_dnd()

    def _try_enable_dnd(self) -> None:
        """Attempt to register drag-and-drop via tkinterdnd2.

        If tkinterdnd2 is not available, silently fallback to button-only.
        Decision: tkinterdnd2 is optional — bundling with PyInstaller is
        known to be problematic. Documented in LIMITATIONS.md.
        """
        try:
            # tkinterdnd2 must be available and the root must support it
            root = self.winfo_toplevel()
            if hasattr(root, "drop_target_register"):
                root.drop_target_register("DND_Files")
                root.dnd_bind("<<Drop>>", self._handle_dnd_drop)
                self._dnd_available = True
        except Exception:
            # tkinterdnd2 not available — button-only mode
            self._dnd_available = False
            self._label.configure(text="📄 Pilih file PDF untuk dikompresi")

    def _handle_dnd_drop(self, event) -> None:
        """Handle drag-and-drop event from tkinterdnd2."""
        # tkinterdnd2 returns paths as space-separated string
        # Paths with spaces are wrapped in {}
        raw = event.data
        paths: list[Path] = []

        if raw.startswith("{"):
            # Parse brace-delimited paths
            import re
            for match in re.finditer(r"\{([^}]+)\}", raw):
                paths.append(Path(match.group(1)))
        else:
            for part in raw.split():
                paths.append(Path(part))

        if paths:
            self._on_files_dropped(paths)

    def _open_file_dialog(self) -> None:
        """Open a file selection dialog for PDFs."""
        files = filedialog.askopenfilenames(
            title="Pilih File PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if files:
            paths = [Path(f) for f in files]
            self._on_files_dropped(paths)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the pick button."""
        self._pick_btn.configure(state="normal" if enabled else "disabled")
