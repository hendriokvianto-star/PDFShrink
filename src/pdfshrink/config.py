"""Configuration management for PDF Shrink.

Reads/writes settings to %APPDATA%\\PDFShrink\\config.json.
Graceful fallback to defaults on corrupt/missing file.
Never raises — always returns a valid AppConfig.

Schema version 1:
  - version: int
  - output_dir: str (absolute path)
  - last_min_kb: int
  - last_max_kb: int
  - appearance: str ("System" | "Dark" | "Light")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Location: %APPDATA%\PDFShrink
_APP_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "PDFShrink"
_CONFIG_FILE = _APP_DIR / "config.json"
_LOG_DIR = _APP_DIR / "logs"

# Schema version — bump when adding/removing fields
_SCHEMA_VERSION = 1

# Default output folder
_DEFAULT_OUTPUT = str(Path.home() / "Documents" / "PDF Shrink")


@dataclass
class AppConfig:
    """Application configuration with defaults.

    Attributes:
        version: Schema version number.
        output_dir: Directory for compressed PDF output.
        last_min_kb: Last-used minimum KB setting.
        last_max_kb: Last-used maximum KB setting.
        appearance: CustomTkinter appearance mode.
    """

    version: int = _SCHEMA_VERSION
    output_dir: str = field(default_factory=lambda: _DEFAULT_OUTPUT)
    last_min_kb: int = 0
    last_max_kb: int = 500
    appearance: str = "System"


def get_app_dir() -> Path:
    """Return the application data directory, creating it if needed."""
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    return _APP_DIR


def get_log_dir() -> Path:
    """Return the log directory, creating it if needed."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def load_config() -> AppConfig:
    """Load configuration from disk.

    Returns default config if file is missing, corrupt, or unreadable.
    Never raises.
    """
    if not _CONFIG_FILE.exists():
        logger.debug("Config file not found, using defaults")
        return AppConfig()

    try:
        raw = _CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)

        if not isinstance(data, dict):
            logger.warning("Config file is not a JSON object, using defaults")
            return AppConfig()

        # Extract known fields with type checking
        config = AppConfig()

        if isinstance(data.get("output_dir"), str):
            config.output_dir = data["output_dir"]

        if isinstance(data.get("last_min_kb"), int):
            config.last_min_kb = max(0, data["last_min_kb"])

        if isinstance(data.get("last_max_kb"), int) and data["last_max_kb"] > 0:
            config.last_max_kb = data["last_max_kb"]

        if data.get("appearance") in ("System", "Dark", "Light"):
            config.appearance = data["appearance"]

        logger.debug("Config loaded from %s", _CONFIG_FILE)
        return config

    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        logger.warning("Failed to load config: %s — using defaults", e)
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to disk.

    Creates the config directory if needed. Logs but does not raise
    on write errors.

    Args:
        config: The configuration to persist.
    """
    try:
        _APP_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(config)
        data["version"] = _SCHEMA_VERSION

        _CONFIG_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Config saved to %s", _CONFIG_FILE)
    except OSError as e:
        logger.error("Failed to save config: %s", e)


def setup_logging() -> None:
    """Configure application logging.

    Sets up a RotatingFileHandler at %APPDATA%\\PDFShrink\\logs\\app.log
    with 5 backup files × 1 MB each. Console handler for DEBUG during
    development.

    Rule: Never log document content. Only filename, size, params,
    duration, error type.
    """
    from logging.handlers import RotatingFileHandler

    log_dir = get_log_dir()
    log_file = log_dir / "app.log"

    # Root logger for pdfshrink namespace
    root = logging.getLogger("pdfshrink")
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if root.handlers:
        return

    # File handler — rotating 5×1MB
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,  # 1 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # Console handler (INFO level for production)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    logger.info("Logging initialized — log file: %s", log_file)


def install_crash_handler() -> None:
    """Install sys.excepthook for unhandled exceptions.

    Shows a user-friendly message and directs to the log file.
    The full traceback is written to the log.
    """
    import sys
    import traceback

    log_file = get_log_dir() / "app.log"

    def _crash_handler(exc_type, exc_value, exc_tb):
        # Log the full traceback
        logger.critical(
            "Unhandled exception: %s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

        # Print user-friendly message
        print(
            f"\n[ERROR] PDF Shrink mengalami error yang tidak terduga.\n"
            f"Detail tersimpan di: {log_file}\n"
            f"Error: {exc_value}\n",
            file=sys.stderr,
        )

    sys.excepthook = _crash_handler
