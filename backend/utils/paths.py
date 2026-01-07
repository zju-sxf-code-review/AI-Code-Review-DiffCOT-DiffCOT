"""
Unified path management for DiffCOT.

Handles different paths for development vs packaged (PyInstaller) environments.
In packaged mode, user data is stored in platform-specific user directories.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Application name for user directories
APP_NAME = "DiffCOT"


def is_packaged() -> bool:
    """Check if running as a packaged PyInstaller executable."""
    # PyInstaller sets sys.frozen when running as exe
    return getattr(sys, 'frozen', False)


def get_app_root() -> Path:
    """Get the application root directory.

    - Development: Project backend directory
    - Packaged: Directory containing the executable
    """
    if is_packaged():
        # PyInstaller: sys._MEIPASS is the temp extraction folder
        # For the actual exe location, use sys.executable's parent
        return Path(sys.executable).parent
    else:
        # Development: backend directory (where main.py is)
        return Path(__file__).parent.parent


def get_user_data_dir() -> Path:
    """Get the user data directory for storing databases, reviews, etc.

    Platform-specific locations:
    - macOS: ~/Library/Application Support/DiffCOT/
    - Windows: %APPDATA%/DiffCOT/
    - Linux: ~/.config/DiffCOT/

    In development mode, returns backend/data for convenience.
    """
    if not is_packaged():
        # Development mode: use local data directory
        data_dir = get_app_root() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    # Packaged mode: use platform-specific user directory
    if sys.platform == "darwin":
        # macOS
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        # Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    else:
        # Linux and others
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            base = Path(xdg_config)
        else:
            base = Path.home() / ".config"

    user_data_dir = base / APP_NAME
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir


def get_database_path() -> Path:
    """Get the path for the SQLite database file."""
    return get_user_data_dir() / "conversations.db"


def get_reviews_dir() -> Path:
    """Get the directory for storing review JSON files."""
    reviews_dir = get_user_data_dir() / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    return reviews_dir


def get_logs_dir() -> Path:
    """Get the directory for log files."""
    logs_dir = get_user_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_dir() -> Path:
    """Get the directory for configuration files."""
    config_dir = get_user_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_bundled_resources_dir() -> Path:
    """Get the directory containing bundled resources (semgrep rules, etc.).

    - Development: backend/configs
    - Packaged: Resources bundled with the executable
    """
    if is_packaged():
        # PyInstaller: _MEIPASS contains extracted resources
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return Path(meipass) / "configs"
        # Fallback to exe directory
        return get_app_root() / "configs"
    else:
        # Development: backend/configs
        return get_app_root() / "configs"


# Convenience exports for commonly used paths
def get_semgrep_rules_path() -> Path:
    """Get the path to custom Semgrep rules."""
    return get_bundled_resources_dir() / "semgrep_rules" / "custom_rules.yaml"


# Print paths info when module loads (for debugging)
def _log_paths():
    """Log path configuration (called on import in debug mode)."""
    import logging
    logger = logging.getLogger(__name__)

    logger.debug(f"Running as packaged: {is_packaged()}")
    logger.debug(f"App root: {get_app_root()}")
    logger.debug(f"User data dir: {get_user_data_dir()}")
    logger.debug(f"Database path: {get_database_path()}")
    logger.debug(f"Reviews dir: {get_reviews_dir()}")


# Only log in debug mode
if os.environ.get("DIFFCOT_DEBUG"):
    _log_paths()
