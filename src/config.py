"""Configuration management for IPO Alerting System."""

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Default watchlist file paths
IPO_WATCHLIST_FILE = Path(__file__).parent.parent / "ipoWatchList.txt"
VOLATILITY_WATCHLIST_FILE = Path(__file__).parent.parent / "volatilityWatchList.txt"
UPCOMING_IPO_WATCHLIST_FILE = Path(__file__).parent.parent / "upcomingIPOList.txt"

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
    upcoming_ipo_bot: BotConfig

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

        if not vol_token:
            vol_token = ipo_token
        if not vol_chat_id:
            vol_chat_id = ipo_chat_id

        # Upcoming IPO Bot configuration (falls back to IPO bot if not configured)
        upcoming_token = os.environ.get("UPCOMING_IPO_BOT_TOKEN")
        upcoming_chat_id = os.environ.get("UPCOMING_IPO_CHAT_ID")

        if not upcoming_token:
            upcoming_token = get_from_keychain("UPCOMING_IPO_BOT_TOKEN")
        if not upcoming_chat_id:
            upcoming_chat_id = get_from_keychain("UPCOMING_IPO_CHAT_ID")

        if not upcoming_token:
            upcoming_token = ipo_token
        if not upcoming_chat_id:
            upcoming_chat_id = ipo_chat_id

        return cls(
            ipo_bot=BotConfig(bot_token=ipo_token, chat_id=ipo_chat_id),
            volatility_bot=BotConfig(bot_token=vol_token, chat_id=vol_chat_id),
            upcoming_ipo_bot=BotConfig(bot_token=upcoming_token, chat_id=upcoming_chat_id),
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


def get_upcoming_ipo_watchlist() -> List[Tuple[str, Optional[str]]]:
    """Load upcoming IPO symbols from upcomingIPOList.txt.

    Format: SYMBOL or SYMBOL:YYYY-MM-DD

    Returns:
        List of tuples (symbol, expected_date_str or None)
    """
    watchlist_path = os.environ.get("UPCOMING_IPO_WATCHLIST_FILE", UPCOMING_IPO_WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)

    if not watchlist_path.exists():
        return []

    entries = []
    with open(watchlist_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse SYMBOL:DATE or just SYMBOL
            if ":" in line:
                parts = line.split(":", 1)
                symbol = parts[0].strip().upper()
                date_str = parts[1].strip() if len(parts) > 1 else None
                entries.append((symbol, date_str))
            else:
                entries.append((line.upper(), None))

    return entries
