"""Configuration management for IPO Alerting System."""

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Default watchlist file paths
IPO_WATCHLIST_FILE = Path(__file__).parent.parent / "ipoWatchList.txt"
VOLATILITY_WATCHLIST_FILE = Path(__file__).parent.parent / "volatilityWatchList.txt"

# Keychain service name for local secrets
KEYCHAIN_ACCOUNT = "IPOAlertingSystem"


def get_from_keychain(service: str) -> Optional[str]:
    """Retrieve a secret from macOS Keychain."""
    if platform.system() != "Darwin":
        return None

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", service, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


@dataclass
class Config:
    """Application configuration loaded from environment variables or Keychain."""

    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables, falling back to Keychain on macOS."""
        # Try environment variables first (for GitHub Actions)
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        # Fall back to Keychain for local development on macOS
        if not bot_token:
            bot_token = get_from_keychain("TELEGRAM_BOT_TOKEN")
        if not chat_id:
            chat_id = get_from_keychain("TELEGRAM_CHAT_ID")

        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment or Keychain")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not found in environment or Keychain")

        return cls(
            telegram_bot_token=bot_token,
            telegram_chat_id=chat_id,
        )


def get_config() -> Config:
    """Get application configuration."""
    return Config.from_env()


def _read_watchlist_file(file_path: Path) -> List[str]:
    """Read symbols from a watchlist file (one symbol per line)."""
    if not file_path.exists():
        return []

    symbols = []
    with open(file_path, "r") as f:
        for line in f:
            symbol = line.strip().upper()
            # Skip empty lines and comments
            if symbol and not symbol.startswith("#"):
                symbols.append(symbol)

    return symbols


def get_ipo_watchlist() -> List[str]:
    """Load ticker symbols from ipoWatchList.txt."""
    watchlist_path = os.environ.get("IPO_WATCHLIST_FILE", IPO_WATCHLIST_FILE)
    return _read_watchlist_file(Path(watchlist_path))


def get_volatility_watchlist() -> List[str]:
    """Load ticker symbols from volatilityWatchList.txt."""
    watchlist_path = os.environ.get("VOLATILITY_WATCHLIST_FILE", VOLATILITY_WATCHLIST_FILE)
    return _read_watchlist_file(Path(watchlist_path))
