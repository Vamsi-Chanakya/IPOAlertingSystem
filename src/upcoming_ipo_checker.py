"""Upcoming IPO checker module - alerts before IPO dates."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .config import UpcomingIPOEntry

logger = logging.getLogger(__name__)

# Alert threshold - days before IPO to send alert
ALERT_DAYS_BEFORE = 2


@dataclass
class UpcomingIPO:
    """Upcoming IPO information."""

    symbol: str
    company_name: Optional[str] = None
    expected_date: Optional[datetime] = None
    exchange: Optional[str] = None
    price_range: Optional[str] = None
    shares: Optional[str] = None
    days_until_ipo: Optional[int] = None
    should_alert: bool = False
    source: str = "manual"

    def format_date(self) -> str:
        """Format the expected date for display."""
        if self.expected_date:
            return self.expected_date.strftime("%Y-%m-%d")
        return "TBD"


class UpcomingIPOChecker:
    """Check for upcoming IPOs and determine if alerts should be sent."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def check_upcoming_ipos(self, watchlist: List["UpcomingIPOEntry"]) -> List[UpcomingIPO]:
        """Check status of upcoming IPOs.

        Args:
            watchlist: List of UpcomingIPOEntry objects from config

        Returns:
            List of UpcomingIPO objects with alert status
        """
        results = []

        # Fetch NASDAQ IPO calendar data
        nasdaq_data = self._fetch_nasdaq_calendar()

        today = datetime.now().date()

        for entry in watchlist:
            ipo = self._check_single_ipo(entry, nasdaq_data, today)
            results.append(ipo)

        return results

    def _check_single_ipo(
        self,
        entry: "UpcomingIPOEntry",
        nasdaq_data: dict,
        today
    ) -> UpcomingIPO:
        """Check a single IPO symbol."""
        ipo = UpcomingIPO(symbol=entry.symbol)

        # Start with manual data from watchlist file
        date_str = entry.expected_date
        if entry.company_name:
            ipo.company_name = entry.company_name
            ipo.source = "manual"
        if entry.price_range:
            ipo.price_range = entry.price_range

        # Check if symbol is in NASDAQ data (to supplement missing info)
        nasdaq_info = nasdaq_data.get(entry.symbol)
        if nasdaq_info:
            # Only use NASDAQ data if manual data not provided
            if not ipo.company_name:
                ipo.company_name = nasdaq_info.get("company_name")
            ipo.exchange = nasdaq_info.get("exchange", "NASDAQ")
            if not ipo.price_range:
                ipo.price_range = nasdaq_info.get("price_range")
            ipo.shares = nasdaq_info.get("shares")
            if not entry.company_name and not entry.price_range:
                ipo.source = "NASDAQ"

            # Use NASDAQ date if no manual date provided
            if not date_str and nasdaq_info.get("expected_date"):
                date_str = nasdaq_info["expected_date"]

        # Parse expected date
        if date_str:
            try:
                ipo.expected_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                # Try other date formats
                for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"]:
                    try:
                        ipo.expected_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue

        # Calculate days until IPO and determine if alert needed
        if ipo.expected_date:
            delta = ipo.expected_date.date() - today
            ipo.days_until_ipo = delta.days

            # Alert if IPO is within ALERT_DAYS_BEFORE days (and not in the past)
            if 0 <= ipo.days_until_ipo <= ALERT_DAYS_BEFORE:
                ipo.should_alert = True

        return ipo

    def _fetch_nasdaq_calendar(self) -> dict:
        """Fetch IPO calendar from NASDAQ API."""
        result = {}

        try:
            url = "https://api.nasdaq.com/api/ipo/calendar"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()

                # Process upcoming, priced, and filed sections
                for section in ["upcoming", "priced", "filed"]:
                    rows = data.get("data", {}).get(section, {}).get("rows", []) or []
                    for row in rows:
                        symbol = (row.get("proposedTickerSymbol") or "").upper()
                        if symbol:
                            # Parse date
                            date_str = row.get("expectedPriceDate") or row.get("pricedDate")
                            expected_date = None
                            if date_str:
                                try:
                                    expected_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
                                except ValueError:
                                    expected_date = date_str

                            result[symbol] = {
                                "company_name": row.get("companyName"),
                                "expected_date": expected_date,
                                "exchange": "NASDAQ",
                                "price_range": row.get("proposedSharePrice"),
                                "shares": row.get("sharesOffered"),
                                "section": section,
                            }

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch NASDAQ IPO calendar: {e}")

        return result

    def fetch_all_upcoming(self) -> List[UpcomingIPO]:
        """Fetch all upcoming IPOs from NASDAQ (for discovery)."""
        results = []
        nasdaq_data = self._fetch_nasdaq_calendar()
        today = datetime.now().date()

        for symbol, info in nasdaq_data.items():
            if info.get("section") in ["upcoming", "filed"]:
                ipo = UpcomingIPO(
                    symbol=symbol,
                    company_name=info.get("company_name"),
                    exchange=info.get("exchange"),
                    price_range=info.get("price_range"),
                    shares=info.get("shares"),
                    source="NASDAQ",
                )

                if info.get("expected_date"):
                    try:
                        ipo.expected_date = datetime.strptime(info["expected_date"], "%Y-%m-%d")
                        delta = ipo.expected_date.date() - today
                        ipo.days_until_ipo = delta.days
                    except ValueError:
                        pass

                results.append(ipo)

        return results


def check_upcoming_ipos(watchlist: List["UpcomingIPOEntry"]) -> List[UpcomingIPO]:
    """Convenience function to check upcoming IPOs."""
    checker = UpcomingIPOChecker()
    return checker.check_upcoming_ipos(watchlist)


def fetch_all_upcoming_ipos() -> List[UpcomingIPO]:
    """Convenience function to fetch all upcoming IPOs."""
    checker = UpcomingIPOChecker()
    return checker.fetch_all_upcoming()
