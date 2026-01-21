"""Configuration management for IPO Alerting System."""

import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

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


@dataclass
class UpcomingIPOEntry:
    """Entry from upcoming IPO watchlist file."""

    symbol: str
    expected_date: Optional[str] = None
    company_name: Optional[str] = None
    price_range: Optional[str] = None


def get_upcoming_ipo_watchlist() -> List[UpcomingIPOEntry]:
    """Load upcoming IPO symbols from upcomingIPOList.txt.

    Format: Space-aligned columns (SYMBOL  DATE  COMPANY  PRICE_RANGE  SOURCE)

    Returns:
        List of UpcomingIPOEntry objects
    """
    import re

    watchlist_path = os.environ.get("UPCOMING_IPO_WATCHLIST_FILE", UPCOMING_IPO_WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)

    if not watchlist_path.exists():
        return []

    entries = []
    with open(watchlist_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines, comments, header row, and separator
            if not line or line.startswith("#") or line.startswith("SYMBOL") or line.startswith("-"):
                continue

            # Parse space-separated columns (split by 2+ spaces)
            parts = re.split(r'\s{2,}', line)
            if not parts:
                continue

            symbol = parts[0].strip().upper()
            entry = UpcomingIPOEntry(symbol=symbol)

            if len(parts) > 1 and parts[1].strip() and parts[1].strip() != "-":
                entry.expected_date = parts[1].strip()
            if len(parts) > 2 and parts[2].strip() and parts[2].strip() != "-":
                entry.company_name = parts[2].strip()
            if len(parts) > 3 and parts[3].strip() and parts[3].strip() != "-":
                entry.price_range = parts[3].strip()

            entries.append(entry)

    return entries


# Upcoming IPO alert and cleanup settings
ALERT_DAYS_BEFORE = 2  # Send alert this many days before IPO
MAX_DAYS_AHEAD = 7     # Only keep IPOs within this many days


def cleanup_upcoming_ipo_watchlist() -> int:
    """Remove past IPOs and IPOs more than MAX_DAYS_AHEAD days away.

    Returns:
        Number of entries removed
    """
    watchlist_path = os.environ.get("UPCOMING_IPO_WATCHLIST_FILE", UPCOMING_IPO_WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)

    if not watchlist_path.exists():
        return 0

    today = datetime.now().date()
    lines_to_keep = []
    removed_count = 0

    with open(watchlist_path, "r") as f:
        for line in f:
            original_line = line
            line = line.strip()

            # Keep comments and empty lines
            if not line or line.startswith("#"):
                lines_to_keep.append(original_line)
                continue

            # Parse the date from the entry
            parts = line.split(":")
            symbol = parts[0].strip().upper()

            # If no date provided, keep the entry
            if len(parts) < 2 or not parts[1].strip():
                lines_to_keep.append(original_line)
                continue

            date_str = parts[1].strip()

            # Try to parse the date
            ipo_date = None
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"]:
                try:
                    ipo_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue

            if ipo_date is None:
                # Can't parse date, keep the entry
                lines_to_keep.append(original_line)
                continue

            # Calculate days until IPO
            days_until = (ipo_date - today).days

            # Remove if date has passed (days_until < 0) or more than MAX_DAYS_AHEAD away
            if days_until < 0:
                logger.info(f"Removing {symbol}: IPO date {date_str} has passed")
                removed_count += 1
            elif days_until > MAX_DAYS_AHEAD:
                logger.info(f"Removing {symbol}: IPO date {date_str} is more than {MAX_DAYS_AHEAD} days away ({days_until} days)")
                removed_count += 1
            else:
                lines_to_keep.append(original_line)

    # Only rewrite the file if entries were removed
    if removed_count > 0:
        with open(watchlist_path, "w") as f:
            f.writelines(lines_to_keep)
        logger.info(f"Cleaned up {removed_count} entries from upcoming IPO watchlist")

    return removed_count


def refresh_upcoming_ipo_watchlist() -> int:
    """Fetch upcoming IPOs from multiple internet sources and update the watchlist file.

    Sources: NASDAQ, Yahoo Finance, IPOScoop, MarketWatch, Webull

    Only includes IPOs within the valid date range (today to today + MAX_DAYS_AHEAD).
    Replaces the entire watchlist with fresh data.

    Returns:
        Number of IPOs added to the watchlist
    """
    # Import here to avoid circular imports
    from .ipo_data_sources import fetch_upcoming_ipos

    watchlist_path = os.environ.get("UPCOMING_IPO_WATCHLIST_FILE", UPCOMING_IPO_WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)

    logger.info("Fetching upcoming IPOs from multiple sources...")
    valid_ipos = fetch_upcoming_ipos(max_days_ahead=MAX_DAYS_AHEAD)

    # Write the watchlist file (properly aligned tabular format)
    sources_list = "NASDAQ, Yahoo Finance, IPOScoop, MarketWatch"

    # Prepare data rows
    rows = []
    for ipo in valid_ipos:
        rows.append({
            "symbol": ipo.symbol,
            "date": ipo.format_date(),
            "company": ipo.company_name or "-",
            "price_range": ipo.price_range or "-",
            "source": ", ".join(ipo.sources),
        })

    # Calculate column widths (minimum widths for headers)
    col_widths = {
        "symbol": max(6, max((len(r["symbol"]) for r in rows), default=0)),
        "date": max(10, max((len(r["date"]) for r in rows), default=0)),
        "company": max(7, max((len(r["company"]) for r in rows), default=0)),
        "price_range": max(11, max((len(r["price_range"]) for r in rows), default=0)),
        "source": max(6, max((len(r["source"]) for r in rows), default=0)),
    }

    # Create format string
    fmt = f"{{:<{col_widths['symbol']}}}  {{:<{col_widths['date']}}}  {{:<{col_widths['company']}}}  {{:<{col_widths['price_range']}}}  {{:<{col_widths['source']}}}"

    # Build header row and separator
    header_row = fmt.format("SYMBOL", "DATE", "COMPANY", "PRICE_RANGE", "SOURCE")
    separator = "-" * len(header_row)

    header = f"""# Upcoming IPO Watchlist (Auto-generated)
#
# Data sources: {sources_list}
# Only IPOs within {MAX_DAYS_AHEAD} days are included
# Alerts are sent {ALERT_DAYS_BEFORE} days before the IPO date
#
# Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{header_row}
{separator}
"""

    with open(watchlist_path, "w") as f:
        f.write(header)
        for row in rows:
            line = fmt.format(row["symbol"], row["date"], row["company"], row["price_range"], row["source"])
            f.write(f"{line}\n")

    logger.info(f"Updated upcoming IPO watchlist with {len(valid_ipos)} IPOs")

    # Also update the IPO watchlist with tickers from upcoming IPOs
    sync_ipo_watchlist_from_upcoming(valid_ipos)

    return len(valid_ipos)


# Days after IPO to keep ticker in watchlist (to catch trading start)
DAYS_AFTER_IPO_TO_KEEP = 2

# State file for tracking IPO dates for watchlist cleanup
IPO_WATCHLIST_DATES_FILE = Path(__file__).parent.parent / "ipo_watchlist_dates.json"


def sync_ipo_watchlist_from_upcoming(upcoming_ipos: list) -> int:
    """Sync ipoWatchList.txt with tickers from upcoming IPOs.

    - Adds new tickers from upcoming IPOs
    - Removes tickers that are past IPO date + DAYS_AFTER_IPO_TO_KEEP
    - Tracks IPO dates in a separate state file

    Returns:
        Number of tickers in the updated watchlist
    """
    import json

    watchlist_path = os.environ.get("IPO_WATCHLIST_FILE", IPO_WATCHLIST_FILE)
    watchlist_path = Path(watchlist_path)
    dates_file = Path(os.environ.get("IPO_WATCHLIST_DATES_FILE", IPO_WATCHLIST_DATES_FILE))

    today = datetime.now().date()

    # Load existing IPO dates tracking
    ipo_dates = {}
    if dates_file.exists():
        try:
            with open(dates_file, "r") as f:
                ipo_dates = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Add new IPOs from upcoming list
    for ipo in upcoming_ipos:
        symbol = ipo.symbol.upper()
        if ipo.expected_date:
            date_str = ipo.expected_date.strftime("%Y-%m-%d")
            if symbol not in ipo_dates:
                logger.info(f"Adding {symbol} to IPO watchlist (IPO date: {date_str})")
            ipo_dates[symbol] = date_str

    # Determine which tickers to keep
    tickers_to_keep = []
    tickers_to_remove = []

    for symbol, date_str in list(ipo_dates.items()):
        try:
            ipo_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            cutoff_date = ipo_date + timedelta(days=DAYS_AFTER_IPO_TO_KEEP)
            days_since_cutoff = (today - cutoff_date).days

            if days_since_cutoff > 0:
                # Past cutoff, remove
                logger.info(f"Removing {symbol} from IPO watchlist (IPO was on {date_str}, {days_since_cutoff} days past cutoff)")
                tickers_to_remove.append(symbol)
            else:
                tickers_to_keep.append(symbol)
        except ValueError:
            # Can't parse date, keep it
            tickers_to_keep.append(symbol)

    # Remove expired tickers from dates tracking
    for symbol in tickers_to_remove:
        del ipo_dates[symbol]

    # Write updated ipoWatchList.txt
    header = f"""# IPO Watchlist (Auto-generated from upcoming IPOs)
# One ticker per line
# Tickers kept until IPO date + {DAYS_AFTER_IPO_TO_KEEP} days
#
# Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

"""

    with open(watchlist_path, "w") as f:
        f.write(header)
        for symbol in sorted(tickers_to_keep):
            f.write(f"{symbol}\n")

    # Save updated dates tracking
    with open(dates_file, "w") as f:
        json.dump(ipo_dates, f, indent=2)

    logger.info(f"Updated IPO watchlist with {len(tickers_to_keep)} tickers")
    return len(tickers_to_keep)
