"""Telegram notification module."""

import logging
from typing import Optional

import requests

from .ipo_checker import IPOInfo, IPOStatus
from .volatility_checker import MovementType, VolatilityInfo
from .upcoming_ipo_checker import UpcomingIPO

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    API_BASE = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"{self.API_BASE}{bot_token}"

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_ipo_alert(self, ipo_info: IPOInfo) -> bool:
        """Send a formatted IPO alert message."""
        emoji = self._get_status_emoji(ipo_info.status)
        status_text = self._get_status_text(ipo_info.status)

        message = f"""
{emoji} <b>IPO Alert: {ipo_info.symbol}</b>

<b>Status:</b> {status_text}
"""

        if ipo_info.company_name:
            message += f"<b>Company:</b> {ipo_info.company_name}\n"

        if ipo_info.exchange:
            message += f"<b>Exchange:</b> {ipo_info.exchange}\n"

        if ipo_info.listing_date:
            message += f"<b>Listing Date:</b> {ipo_info.listing_date}\n"

        if ipo_info.price:
            message += f"<b>Price:</b> ${ipo_info.price}\n"

        if ipo_info.details:
            message += f"\n<i>{ipo_info.details}</i>\n"

        if ipo_info.is_tradeable():
            message += "\n<b>Shares are now available for trading!</b>"

        return self.send_message(message.strip())

    def send_volatility_alert(self, vol_info: VolatilityInfo) -> bool:
        """Send a formatted volatility alert message."""
        if vol_info.movement == MovementType.RALLY:
            emoji = "🚀"
            movement_text = "RALLY"
        else:
            emoji = "📉"
            movement_text = "DROP"

        message = f"""
{emoji} <b>Volatility Alert: {vol_info.symbol}</b>

<b>Movement:</b> {movement_text} ({vol_info.change_percent:+.2f}%)
"""

        if vol_info.company_name:
            message += f"<b>Company:</b> {vol_info.company_name}\n"

        if vol_info.current_price is not None:
            message += f"<b>Current Price:</b> {vol_info.currency} {vol_info.current_price:.2f}\n"

        if vol_info.previous_price is not None:
            message += f"<b>Previous Price:</b> {vol_info.currency} {vol_info.previous_price:.2f}\n"

        return self.send_message(message.strip())

    def send_upcoming_ipo_alert(self, ipo: UpcomingIPO) -> bool:
        """Send a formatted upcoming IPO alert message."""
        if ipo.days_until_ipo == 0:
            emoji = "🚨"
            urgency = "IPO IS TODAY!"
        elif ipo.days_until_ipo == 1:
            emoji = "⚠️"
            urgency = "IPO is TOMORROW!"
        else:
            emoji = "📅"
            urgency = f"IPO in {ipo.days_until_ipo} days"

        message = f"""
{emoji} <b>Upcoming IPO Alert: {ipo.symbol}</b>

<b>{urgency}</b>
"""

        if ipo.company_name:
            message += f"<b>Company:</b> {ipo.company_name}\n"

        if ipo.expected_date:
            message += f"<b>Expected Date:</b> {ipo.format_date()}\n"

        if ipo.exchange:
            message += f"<b>Exchange:</b> {ipo.exchange}\n"

        if ipo.price_range:
            message += f"<b>Price Range:</b> {ipo.price_range}\n"

        if ipo.shares:
            message += f"<b>Shares Offered:</b> {ipo.shares}\n"

        message += f"\n<i>Source: {ipo.source}</i>"

        return self.send_message(message.strip())

    def send_status_update(self, message: str) -> bool:
        """Send a simple status update message."""
        return self.send_message(message)

    def _get_status_emoji(self, status: IPOStatus) -> str:
        """Get emoji for status."""
        emoji_map = {
            IPOStatus.NOT_FOUND: "🔍",
            IPOStatus.UPCOMING: "📅",
            IPOStatus.SUBSCRIPTION_OPEN: "📝",
            IPOStatus.SUBSCRIPTION_CLOSED: "🔒",
            IPOStatus.ALLOTMENT_PENDING: "⏳",
            IPOStatus.ALLOTMENT_DONE: "✅",
            IPOStatus.LISTED: "🎉",
            IPOStatus.TRADING: "📈",
        }
        return emoji_map.get(status, "ℹ️")

    def _get_status_text(self, status: IPOStatus) -> str:
        """Get human-readable status text."""
        text_map = {
            IPOStatus.NOT_FOUND: "Not Found",
            IPOStatus.UPCOMING: "Upcoming",
            IPOStatus.SUBSCRIPTION_OPEN: "Subscription Open",
            IPOStatus.SUBSCRIPTION_CLOSED: "Subscription Closed",
            IPOStatus.ALLOTMENT_PENDING: "Allotment Pending",
            IPOStatus.ALLOTMENT_DONE: "Allotment Complete",
            IPOStatus.LISTED: "Listed",
            IPOStatus.TRADING: "Trading",
        }
        return text_map.get(status, "Unknown")


def send_alert(bot_token: str, chat_id: str, ipo_info: IPOInfo) -> bool:
    """Convenience function to send an IPO alert."""
    notifier = TelegramNotifier(bot_token, chat_id)
    return notifier.send_ipo_alert(ipo_info)
