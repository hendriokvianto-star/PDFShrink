"""Size input widgets for min/max KB target configuration.

Provides validated integer inputs with real-time validation feedback.
Red error label displayed when max <= min.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class SizeInputs(ctk.CTkFrame):
    """Min/Max KB input frame with validation.

    Attributes:
        min_var: StringVar holding the minimum KB value.
        max_var: StringVar holding the maximum KB value.
        is_valid: Whether current min/max values are valid.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_validation_change: Callable[[bool], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_validation_change = on_validation_change

        # --- Header ---
        header = ctk.CTkLabel(
            self,
            text="Ukuran target",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 6))

        # --- Input row ---
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        # Min input
        ctk.CTkLabel(
            row, text="Minimum", font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left")

        self.min_var = ctk.StringVar(value="0")
        self._min_entry = ctk.CTkEntry(
            row, width=80, textvariable=self.min_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            justify="right",
        )
        self._min_entry.pack(side="left", padx=(6, 2))

        ctk.CTkLabel(
            row, text="KB", font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left", padx=(0, 16))

        # Max input
        ctk.CTkLabel(
            row, text="Maksimum", font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left")

        self.max_var = ctk.StringVar(value="500")
        self._max_entry = ctk.CTkEntry(
            row, width=80, textvariable=self.max_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            justify="right",
        )
        self._max_entry.pack(side="left", padx=(6, 2))

        ctk.CTkLabel(
            row, text="KB", font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left")

        # --- Error label ---
        self._error_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#e74c3c",
            anchor="w",
        )
        self._error_label.pack(fill="x", pady=(4, 0))

        # Validation state
        self.is_valid = True

        # Bind validation
        self.min_var.trace_add("write", self._validate)
        self.max_var.trace_add("write", self._validate)

    def _validate(self, *_args) -> None:
        """Validate min/max values and update error label."""
        min_text = self.min_var.get().strip()
        max_text = self.max_var.get().strip()

        error = ""
        try:
            min_val = int(min_text) if min_text else 0
            max_val = int(max_text) if max_text else 0

            if max_val <= 0:
                error = "Ukuran maksimum harus lebih besar dari 0."
            elif min_val < 0:
                error = "Ukuran minimum tidak boleh negatif."
            elif max_val <= min_val:
                error = "Ukuran maksimum harus lebih besar dari minimum."
        except ValueError:
            error = "Masukkan angka bulat yang valid."

        was_valid = self.is_valid
        self.is_valid = error == ""

        self._error_label.configure(text=error)

        if was_valid != self.is_valid and self._on_validation_change:
            self._on_validation_change(self.is_valid)

    def get_min_kb(self) -> int:
        """Return current min KB value, defaulting to 0."""
        try:
            return int(self.min_var.get().strip())
        except (ValueError, AttributeError):
            return 0

    def get_max_kb(self) -> int:
        """Return current max KB value, defaulting to 500."""
        try:
            return int(self.max_var.get().strip())
        except (ValueError, AttributeError):
            return 500
