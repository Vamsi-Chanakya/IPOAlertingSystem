"""Configuration management for IPO Alerting System."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    telegram_chat_id: str
    ipo_symbol: str = "BITGO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        ipo_symbol = os.environ.get("IPO_SYMBOL", "BITGO")

        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

        return cls(
            telegram_bot_token=bot_token,
            telegram_chat_id=chat_id,
            ipo_symbol=ipo_symbol,
        )


def get_config() -> Config:
    """Get application configuration."""
    return Config.from_env()
