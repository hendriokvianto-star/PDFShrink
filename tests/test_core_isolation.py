"""Tests for core/GUI architecture isolation (AC-17).

Ensures that no module in src/pdfshrink/core/ imports
tkinter or customtkinter. The core package must remain
fully independent of the GUI layer.
"""

from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent.parent / "src" / "pdfshrink" / "core"

FORBIDDEN_GUI_MODULES = {
    "tkinter",
    "customtkinter",
    "_tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
}


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all imported module names from a Python file."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


class TestCoreIsolation:
    """AC-17: core/ must not import GUI modules."""

    def test_no_gui_imports_in_core(self):
        """Scan core/*.py for forbidden tkinter/customtkinter imports."""
        violations: list[str] = []

        for py_file in sorted(CORE_DIR.rglob("*.py")):
            imports = _extract_imports(py_file)
            for imp in imports:
                for forbidden in FORBIDDEN_GUI_MODULES:
                    if imp == forbidden or imp.startswith(forbidden + "."):
                        rel_path = py_file.relative_to(CORE_DIR)
                        violations.append(
                            f"core/{rel_path}: imports '{imp}'"
                        )

        assert not violations, (
            "Found GUI imports in core package (architecture violation):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_core_has_modules(self):
        """Sanity check: core/ should contain Python files."""
        py_files = list(CORE_DIR.rglob("*.py"))
        assert len(py_files) > 0, "No .py files found in core/"
