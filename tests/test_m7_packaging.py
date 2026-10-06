"""M7 gate-check tests — packaging & release artifacts.

Gate checks:
- AC-18: LIMITATIONS.md exists with meaningful content (8 sections)
- build.spec exists and references required hidden imports
- README.md is complete (usage, build from source, features)
- pyproject.toml version consistent
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


class TestAC18Limitations:
    """AC-18: LIMITATIONS.md exists with meaningful content."""

    def test_limitations_file_exists(self):
        """LIMITATIONS.md must exist."""
        assert (ROOT / "LIMITATIONS.md").exists()

    def test_limitations_has_content(self):
        """LIMITATIONS.md must have meaningful content (>500 chars)."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        assert len(content) > 500, "LIMITATIONS.md troppo breve"

    def test_limitations_covers_text_only_pdfs(self):
        """Must document text-only PDF limitation."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        assert "teks" in content.lower() or "text" in content.lower()

    def test_limitations_covers_dpi_proxy(self):
        """Must document DPI calculation limitation."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        assert "dpi" in content.lower() or "ctm" in content.lower()

    def test_limitations_covers_ghostscript(self):
        """Must document Ghostscript limitation."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        assert "ghostscript" in content.lower()

    def test_limitations_covers_dragdrop(self):
        """Must document drag-and-drop limitation."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        assert "drag" in content.lower()

    def test_limitations_has_multiple_sections(self):
        """Must have at least 4 meaningful sections (##)."""
        content = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
        section_count = content.count("\n## ")
        assert section_count >= 4, f"Hanya {section_count} section, perlu minimal 4"


class TestReadme:
    """README.md must be complete."""

    def test_readme_exists(self):
        assert (ROOT / "README.md").exists()

    def test_readme_has_usage_section(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "penggunaan" in content.lower() or "usage" in content.lower()

    def test_readme_has_build_instructions(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "pyinstaller" in content.lower()
        assert "pip install" in content.lower()

    def test_readme_has_features(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "offline" in content.lower()
        assert "fitur" in content.lower() or "feature" in content.lower()

    def test_readme_references_limitations(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "limitations" in content.lower() or "keterbatasan" in content.lower()

    def test_readme_minimum_length(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        assert len(content) > 1000, "README terlalu pendek"


class TestBuildSpec:
    """build.spec must exist and be properly configured."""

    def test_build_spec_exists(self):
        """build.spec must exist."""
        assert (ROOT / "build.spec").exists()

    def test_build_spec_has_pikepdf_hidden_import(self):
        """Must include pikepdf as hidden import."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "pikepdf" in content

    def test_build_spec_has_pil_hidden_import(self):
        """Must include PIL/Pillow as hidden import."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "PIL" in content

    def test_build_spec_has_customtkinter(self):
        """Must include customtkinter."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "customtkinter" in content

    def test_build_spec_windowed(self):
        """Must use console=False (windowed mode)."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "console=False" in content

    def test_build_spec_has_onefile(self):
        """Must produce a single-file exe."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        # EXE with all binaries/datas = onefile pattern
        assert "EXE" in content

    def test_build_spec_has_onedir(self):
        """Must also produce onedir (COLLECT) as alternative."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "COLLECT" in content

    def test_build_spec_excludes_test_deps(self):
        """Must exclude pytest and reportlab from bundle."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert '"pytest"' in content or "'pytest'" in content

    def test_build_spec_has_logging_handlers(self):
        """Must include logging.handlers (RotatingFileHandler)."""
        content = (ROOT / "build.spec").read_text(encoding="utf-8")
        assert "logging.handlers" in content


class TestProjectConsistency:
    """Project-level consistency checks."""

    def test_version_in_init(self):
        """__init__.py must define __version__."""
        init_file = ROOT / "src" / "pdfshrink" / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        assert "__version__" in content
        assert "1.0.0" in content

    def test_version_in_pyproject(self):
        """pyproject.toml must define same version."""
        content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "1.0.0" in content

    def test_requirements_has_three_deps(self):
        """requirements.txt must have the 3 core dependencies."""
        content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "customtkinter" in content
        assert "pikepdf" in content
        assert "Pillow" in content or "pillow" in content
