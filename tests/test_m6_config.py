"""M6 gate-check tests — config persistence and logging rotation.

Gate checks:
- Settings persist after app restart (config.json round-trip)
- Log file created with correct rotation setup
- Crash handler installed
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from pdfshrink.config import (
    AppConfig,
    _CONFIG_FILE,
    _LOG_DIR,
    get_app_dir,
    get_log_dir,
    install_crash_handler,
    load_config,
    save_config,
    setup_logging,
)


class TestAppConfig:
    """Test AppConfig defaults and structure."""

    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.version == 1
        assert cfg.last_min_kb == 0
        assert cfg.last_max_kb == 500
        assert cfg.appearance == "System"
        assert "PDF Shrink" in cfg.output_dir

    def test_custom_values(self):
        cfg = AppConfig(last_min_kb=100, last_max_kb=1000, appearance="Dark")
        assert cfg.last_min_kb == 100
        assert cfg.last_max_kb == 1000
        assert cfg.appearance == "Dark"


class TestConfigPersistence:
    """Gate check: settings persist after app restart."""

    def test_save_and_load_round_trip(self, tmp_path: Path):
        """Config saves to JSON and loads back with same values."""
        config_file = tmp_path / "config.json"

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file), \
             mock.patch("pdfshrink.config._APP_DIR", tmp_path):
            # Save custom config
            cfg = AppConfig(
                output_dir=str(tmp_path / "output"),
                last_min_kb=50,
                last_max_kb=800,
                appearance="Dark",
            )
            save_config(cfg)

            # Verify file exists
            assert config_file.exists()

            # Load it back
            loaded = load_config()
            assert loaded.output_dir == str(tmp_path / "output")
            assert loaded.last_min_kb == 50
            assert loaded.last_max_kb == 800
            assert loaded.appearance == "Dark"
            assert loaded.version == 1

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        """Missing config returns defaults, no error."""
        config_file = tmp_path / "nonexistent.json"

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.last_max_kb == 500
            assert cfg.appearance == "System"

    def test_load_corrupt_json_returns_defaults(self, tmp_path: Path):
        """Corrupt JSON returns defaults gracefully."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json!!!}", encoding="utf-8")

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.last_max_kb == 500

    def test_load_partial_config_fills_defaults(self, tmp_path: Path):
        """Partial JSON fills missing fields with defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"last_max_kb": 1500}), encoding="utf-8",
        )

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.last_max_kb == 1500
            assert cfg.last_min_kb == 0  # default
            assert cfg.appearance == "System"  # default

    def test_load_invalid_appearance_uses_default(self, tmp_path: Path):
        """Invalid appearance value falls back to default."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"appearance": "invalid_mode"}), encoding="utf-8",
        )

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.appearance == "System"

    def test_negative_min_kb_clamped(self, tmp_path: Path):
        """Negative min_kb clamped to 0."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"last_min_kb": -10}), encoding="utf-8",
        )

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.last_min_kb == 0

    def test_zero_max_kb_uses_default(self, tmp_path: Path):
        """Zero max_kb uses default."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"last_max_kb": 0}), encoding="utf-8",
        )

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.last_max_kb == 500  # default

    def test_config_json_format(self, tmp_path: Path):
        """Saved config is human-readable JSON with indentation."""
        config_file = tmp_path / "config.json"

        with mock.patch("pdfshrink.config._CONFIG_FILE", config_file), \
             mock.patch("pdfshrink.config._APP_DIR", tmp_path):
            save_config(AppConfig())

            raw = config_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            assert "version" in data
            assert "output_dir" in data
            # Verify indentation
            assert "\n  " in raw


class TestLogging:
    """Gate check: log file created with correct rotation."""

    def test_setup_logging_creates_log_file(self, tmp_path: Path):
        """setup_logging creates a log file at the expected path."""
        log_dir = tmp_path / "logs"

        with mock.patch("pdfshrink.config._LOG_DIR", log_dir), \
             mock.patch("pdfshrink.config._APP_DIR", tmp_path):
            # Clear any existing handlers
            test_logger = logging.getLogger("pdfshrink")
            test_logger.handlers.clear()

            setup_logging()

            # Write a test message
            test_logger.info("Test log message")

            # Verify log file exists and has content
            log_file = log_dir / "app.log"
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "Test log message" in content

            # Clean up handlers
            test_logger.handlers.clear()

    def test_rotating_handler_config(self, tmp_path: Path):
        """RotatingFileHandler configured with 5×1MB."""
        from logging.handlers import RotatingFileHandler

        log_dir = tmp_path / "logs"

        with mock.patch("pdfshrink.config._LOG_DIR", log_dir), \
             mock.patch("pdfshrink.config._APP_DIR", tmp_path):
            test_logger = logging.getLogger("pdfshrink")
            test_logger.handlers.clear()

            setup_logging()

            # Find the rotating handler
            rotating_handlers = [
                h for h in test_logger.handlers
                if isinstance(h, RotatingFileHandler)
            ]
            assert len(rotating_handlers) == 1

            rh = rotating_handlers[0]
            assert rh.maxBytes == 1_048_576  # 1 MB
            assert rh.backupCount == 5

            test_logger.handlers.clear()


class TestCrashHandler:
    """Gate check: sys.excepthook installed."""

    def test_install_crash_handler(self):
        """install_crash_handler sets sys.excepthook."""
        original = sys.excepthook
        try:
            install_crash_handler()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original

    def test_crash_handler_logs_and_prints(self, tmp_path: Path, capsys):
        """Crash handler logs traceback and prints user-friendly message."""
        log_dir = tmp_path / "logs"

        with mock.patch("pdfshrink.config._LOG_DIR", log_dir), \
             mock.patch("pdfshrink.config._APP_DIR", tmp_path):
            original = sys.excepthook
            try:
                test_logger = logging.getLogger("pdfshrink")
                test_logger.handlers.clear()
                setup_logging()
                install_crash_handler()

                # Simulate an unhandled exception
                try:
                    raise ValueError("test crash")
                except ValueError:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    sys.excepthook(exc_type, exc_value, exc_tb)

                # Check stderr output
                captured = capsys.readouterr()
                assert "error yang tidak terduga" in captured.err
                assert "test crash" in captured.err

                # Check log file
                log_file = log_dir / "app.log"
                log_content = log_file.read_text(encoding="utf-8")
                assert "test crash" in log_content

                test_logger.handlers.clear()
            finally:
                sys.excepthook = original


class TestDirectoryHelpers:
    """Test get_app_dir and get_log_dir."""

    def test_get_app_dir_creates_directory(self, tmp_path: Path):
        with mock.patch("pdfshrink.config._APP_DIR", tmp_path / "new_dir"):
            result = get_app_dir()
            assert result.exists()
            assert result.is_dir()

    def test_get_log_dir_creates_directory(self, tmp_path: Path):
        with mock.patch("pdfshrink.config._LOG_DIR", tmp_path / "new_logs"):
            result = get_log_dir()
            assert result.exists()
            assert result.is_dir()
