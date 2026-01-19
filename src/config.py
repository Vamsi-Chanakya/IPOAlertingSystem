"""Configuration management for IPO Alerting System."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Default watchlist file path
WATCHLIST_FILE = Path(__file__).parent.parent / "watchlist.txt"


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

        return cls(
            telegram_bot_token=bot_token,
            telegram_chat_id=chat_id,
        )


def get_config() -> Config:
    """Get application configuration."""
    return Config.from_env()


def get_watchlist() -> List[str]:
    """Load ticker symbols from watchlist.txt (one symbol per line)."""
    watchlist_path = os.environ.get("WATCHLIST_FILE", WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)

    if not watchlist_path.exists():
        raise FileNotFoundError(f"Watchlist file not found: {watchlist_path}")

    symbols = []
    with open(watchlist_path, "r") as f:
        for line in f:
            symbol = line.strip().upper()
            # Skip empty lines and comments
            if symbol and not symbol.startswith("#"):
                symbols.append(symbol)

    if not symbols:
        raise ValueError("Watchlist file is empty")

    return symbols
