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
class BotConfig:
    """Telegram bot configuration."""

    bot_token: str
    chat_id: str


@dataclass
class Config:
    """Application configuration loaded from environment variables or Keychain."""

    ipo_bot: BotConfig
    volatility_bot: BotConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables, falling back to Keychain on macOS."""
        # IPO Bot configuration
        ipo_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        ipo_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not ipo_token:
            ipo_token = get_from_keychain("TELEGRAM_BOT_TOKEN")
        if not ipo_chat_id:
            ipo_chat_id = get_from_keychain("TELEGRAM_CHAT_ID")

        if not ipo_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment or Keychain")
        if not ipo_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not found in environment or Keychain")

        # Volatility Bot configuration (falls back to IPO bot if not configured)
        vol_token = os.environ.get("VOLATILITY_BOT_TOKEN")
        vol_chat_id = os.environ.get("VOLATILITY_CHAT_ID")

        if not vol_token:
            vol_token = get_from_keychain("VOLATILITY_BOT_TOKEN")
        if not vol_chat_id:
            vol_chat_id = get_from_keychain("VOLATILITY_CHAT_ID")

        # Fall back to IPO bot if volatility bot not configured
        if not vol_token:
            vol_token = ipo_token
        if not vol_chat_id:
            vol_chat_id = ipo_chat_id

        return cls(
            ipo_bot=BotConfig(bot_token=ipo_token, chat_id=ipo_chat_id),
            volatility_bot=BotConfig(bot_token=vol_token, chat_id=vol_chat_id),
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
