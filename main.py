#!/usr/bin/env python3
"""IPO Alerting System - Main Entry Point.

This script checks the IPO status for a configured symbol and sends
Telegram alerts when the status changes or shares become available for trading.
"""

import json
import logging
import os
import sys
from pathlib import Path

from src.config import get_config
from src.ipo_checker import IPOInfo, IPOStatus, check_ipo_status
from src.telegram_notifier import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# State file for tracking previous status
STATE_FILE = Path("ipo_state.json")


def load_previous_state() -> dict:
    """Load the previous IPO state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state file: {e}")
    return {}


def save_state(ipo_info: IPOInfo) -> None:
    """Save the current IPO state to file."""
    state = {
        "symbol": ipo_info.symbol,
        "status": ipo_info.status.value,
        "company_name": ipo_info.company_name,
        "exchange": ipo_info.exchange,
        "price": ipo_info.price,
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save state file: {e}")


def should_send_alert(current_info: IPOInfo, previous_state: dict) -> bool:
    """Determine if an alert should be sent based on status change.

    Only sends alerts for these 3 specific events:
    1. IPO subscription opens
    2. Allotment results are announced
    3. Shares become available for trading
    """
    previous_status = previous_state.get("status")
    current_status = current_info.status

    # Don't alert if status hasn't changed
    if previous_status == current_status.value:
        return False

    # Only alert for these 3 specific events
    alert_statuses = (
        IPOStatus.SUBSCRIPTION_OPEN,  # Subscription opens
        IPOStatus.ALLOTMENT_DONE,     # Allotment results announced
        IPOStatus.LISTED,             # Shares available for trading
        IPOStatus.TRADING,            # Shares available for trading
    )

    return current_status in alert_statuses


def main() -> int:
    """Main entry point."""
    logger.info("Starting IPO Alerting System")

    # Load configuration
    try:
        config = get_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    logger.info(f"Checking IPO status for: {config.ipo_symbol}")

    # Check IPO status
    ipo_info = check_ipo_status(config.ipo_symbol)
    logger.info(f"IPO Status: {ipo_info.status.value}")

    if ipo_info.company_name:
        logger.info(f"Company: {ipo_info.company_name}")
    if ipo_info.price:
        logger.info(f"Price: ${ipo_info.price}")

    # Load previous state
    previous_state = load_previous_state()
    previous_status = previous_state.get("status", "unknown")
    logger.info(f"Previous status: {previous_status}")

    # Initialize notifier
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)

    # Determine if we should send an alert
    if should_send_alert(ipo_info, previous_state):
        logger.info("Status change detected - sending alert")
        if notifier.send_ipo_alert(ipo_info):
            logger.info("Alert sent successfully")
        else:
            logger.error("Failed to send alert")
    else:
        logger.info("No alert conditions met - skipping notification")

    # Save current state
    save_state(ipo_info)

    logger.info("IPO check complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
