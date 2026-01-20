#!/usr/bin/env python3
"""IPO and Volatility Alerting System - Main Entry Point.

This script checks:
1. IPO status for symbols in ipoWatchList.txt
2. Price volatility for symbols in volatilityWatchList.txt

Sends Telegram alerts when conditions are met.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict

from src.config import get_config, get_ipo_watchlist, get_volatility_watchlist
from src.ipo_checker import IPOInfo, IPOStatus, check_ipo_status
from src.volatility_checker import VolatilityInfo, check_volatility
from src.telegram_notifier import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# State files for tracking
IPO_STATE_FILE = Path("ipo_state.json")
VOLATILITY_STATE_FILE = Path("volatility_state.json")


def load_state(state_file: Path) -> Dict[str, dict]:
    """Load previous states from file."""
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state file {state_file}: {e}")
    return {}


def save_state(state_file: Path, states: Dict[str, dict]) -> None:
    """Save states to file."""
    try:
        with open(state_file, "w") as f:
            json.dump(states, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save state file {state_file}: {e}")


def should_send_ipo_alert(current_info: IPOInfo, previous_state: dict) -> bool:
    """Determine if an IPO alert should be sent.

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

    # Only alert for these specific events
    alert_statuses = (
        IPOStatus.SUBSCRIPTION_OPEN,
        IPOStatus.ALLOTMENT_DONE,
        IPOStatus.LISTED,
        IPOStatus.TRADING,
    )

    return current_status in alert_statuses


def check_ipo_symbol(symbol: str, notifier: TelegramNotifier, states: Dict[str, dict]) -> None:
    """Check a single IPO symbol and send alert if needed."""
    logger.info(f"[IPO] Checking: {symbol}")

    ipo_info = check_ipo_status(symbol)
    logger.info(f"  Status: {ipo_info.status.value}")

    if ipo_info.company_name:
        logger.info(f"  Company: {ipo_info.company_name}")
    if ipo_info.price:
        logger.info(f"  Price: ${ipo_info.price}")

    previous_state = states.get(symbol, {})
    previous_status = previous_state.get("status", "unknown")
    logger.info(f"  Previous status: {previous_status}")

    if should_send_ipo_alert(ipo_info, previous_state):
        logger.info(f"  Alert condition met - sending notification")
        if notifier.send_ipo_alert(ipo_info):
            logger.info(f"  Alert sent successfully")
        else:
            logger.error(f"  Failed to send alert")
    else:
        logger.info(f"  No alert conditions met")

    states[symbol] = {
        "status": ipo_info.status.value,
        "company_name": ipo_info.company_name,
        "exchange": ipo_info.exchange,
        "price": ipo_info.price,
    }


def check_volatility_symbol(symbol: str, notifier: TelegramNotifier, states: Dict[str, dict]) -> None:
    """Check a single volatility symbol and send alert if needed."""
    logger.info(f"[Volatility] Checking: {symbol}")

    previous_state = states.get(symbol, {})
    previous_price = previous_state.get("price")

    vol_info = check_volatility(symbol, previous_price)

    if vol_info.error:
        logger.warning(f"  Error: {vol_info.error}")
        return

    if vol_info.current_price:
        logger.info(f"  Current price: {vol_info.currency} {vol_info.current_price:.2f}")
    if vol_info.company_name:
        logger.info(f"  Company: {vol_info.company_name}")
    if previous_price:
        logger.info(f"  Previous price: {vol_info.currency} {previous_price:.2f}")
    if vol_info.change_percent is not None:
        logger.info(f"  Change: {vol_info.change_percent:+.2f}%")

    if vol_info.has_significant_movement():
        logger.info(f"  Significant {vol_info.movement.value} detected - sending alert")
        if notifier.send_volatility_alert(vol_info):
            logger.info(f"  Alert sent successfully")
        else:
            logger.error(f"  Failed to send alert")
    else:
        logger.info(f"  No significant movement")

    # Update state
    if vol_info.current_price:
        states[symbol] = {
            "price": vol_info.current_price,
            "company_name": vol_info.company_name,
            "currency": vol_info.currency,
        }


def main() -> int:
    """Main entry point."""
    logger.info("Starting Alerting System")

    # Load configuration
    try:
        config = get_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Initialize separate notifiers for IPO and Volatility
    ipo_notifier = TelegramNotifier(config.ipo_bot.bot_token, config.ipo_bot.chat_id)
    volatility_notifier = TelegramNotifier(config.volatility_bot.bot_token, config.volatility_bot.chat_id)

    # Process IPO watchlist
    ipo_watchlist = get_ipo_watchlist()
    if ipo_watchlist:
        logger.info(f"IPO Watchlist: {len(ipo_watchlist)} symbol(s): {', '.join(ipo_watchlist)}")
        ipo_states = load_state(IPO_STATE_FILE)
        for symbol in ipo_watchlist:
            check_ipo_symbol(symbol, ipo_notifier, ipo_states)
        save_state(IPO_STATE_FILE, ipo_states)
    else:
        logger.info("IPO Watchlist: empty")

    # Process volatility watchlist
    volatility_watchlist = get_volatility_watchlist()
    if volatility_watchlist:
        logger.info(f"Volatility Watchlist: {len(volatility_watchlist)} symbol(s): {', '.join(volatility_watchlist)}")
        volatility_states = load_state(VOLATILITY_STATE_FILE)
        for symbol in volatility_watchlist:
            check_volatility_symbol(symbol, volatility_notifier, volatility_states)
        save_state(VOLATILITY_STATE_FILE, volatility_states)
    else:
        logger.info("Volatility Watchlist: empty")

    logger.info("Check complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
