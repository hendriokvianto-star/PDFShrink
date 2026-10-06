"""Tests for network import prohibition (AC-16).

Scans all .py files in src/ for forbidden network-related imports.
PDF Shrink must be 100% offline — zero network I/O.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"

FORBIDDEN_MODULES = {
    "socket",
    "requests",
    "urllib.request",
    "httpx",
    "http.client",
    "http.server",
    "ftplib",
    "smtplib",
    "xmlrpc",
    "aiohttp",
    "websocket",
    "websockets",
    "urllib3",
}


def _collect_py_files(directory: Path) -> list[Path]:
    """Collect all .py files recursively."""
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all imported module names from a Python file using AST."""
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


class TestNoNetworkImports:
    """AC-16: No network-related imports in src/."""

    def test_no_forbidden_imports(self):
        """Scan all source files for forbidden network imports."""
        violations: list[str] = []

        for py_file in _collect_py_files(SRC_DIR):
            imports = _extract_imports(py_file)
            for imp in imports:
                # Check if the import matches any forbidden module
                for forbidden in FORBIDDEN_MODULES:
                    if imp == forbidden or imp.startswith(forbidden + "."):
                        rel_path = py_file.relative_to(SRC_DIR)
                        violations.append(
                            f"{rel_path}: imports '{imp}'"
                        )

        assert not violations, (
            "Found forbidden network imports in source code:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_src_has_py_files(self):
        """Sanity check: src/ should contain Python files."""
        py_files = _collect_py_files(SRC_DIR)
        assert len(py_files) > 0, "No .py files found in src/"
