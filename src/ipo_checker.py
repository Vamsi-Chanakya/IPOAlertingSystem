"""IPO status checking module."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class IPOStatus(Enum):
    """IPO status enumeration."""

    NOT_FOUND = "not_found"
    UPCOMING = "upcoming"
    SUBSCRIPTION_OPEN = "subscription_open"
    SUBSCRIPTION_CLOSED = "subscription_closed"
    ALLOTMENT_PENDING = "allotment_pending"
    ALLOTMENT_DONE = "allotment_done"
    LISTED = "listed"
    TRADING = "trading"


@dataclass
class IPOInfo:
    """IPO information data class."""

    symbol: str
    status: IPOStatus
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    listing_date: Optional[str] = None
    price: Optional[str] = None
    details: Optional[str] = None

    def is_tradeable(self) -> bool:
        """Check if shares are available for trading."""
        return self.status in (IPOStatus.LISTED, IPOStatus.TRADING)

    def is_actionable(self) -> bool:
        """Check if there's an actionable update (subscription or trading)."""
        return self.status in (
            IPOStatus.SUBSCRIPTION_OPEN,
            IPOStatus.ALLOTMENT_DONE,
            IPOStatus.LISTED,
            IPOStatus.TRADING,
        )


class IPOChecker:
    """Check IPO status from multiple sources."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def check_status(self) -> IPOInfo:
        """Check IPO status from multiple sources."""
        # Try Yahoo Finance API first (most reliable for trading stocks)
        info = self._check_yahoo_finance_api()
        if info and info.status != IPOStatus.NOT_FOUND:
            return info

        # Check NASDAQ IPO calendar for upcoming IPOs
        info = self._check_nasdaq_ipo_calendar()
        if info and info.status != IPOStatus.NOT_FOUND:
            return info

        # Return not found status
        return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

    def _check_yahoo_finance_api(self) -> Optional[IPOInfo]:
        """Check Yahoo Finance API for stock data."""
        try:
            # Use Yahoo Finance quote API
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self.symbol}"
            params = {"interval": "1d", "range": "1d"}
            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result")

                if result and len(result) > 0:
                    meta = result[0].get("meta", {})

                    # Check if this is a valid tradeable stock
                    symbol = meta.get("symbol", "").upper()
                    if symbol != self.symbol:
                        return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

                    price = meta.get("regularMarketPrice")
                    exchange = meta.get("exchangeName")
                    company_name = meta.get("shortName") or meta.get("longName")
                    currency = meta.get("currency", "USD")

                    if price:
                        return IPOInfo(
                            symbol=self.symbol,
                            status=IPOStatus.TRADING,
                            company_name=company_name,
                            exchange=exchange,
                            price=f"{price:.2f}",
                            details=f"Trading on {exchange} at {currency} {price:.2f}",
                        )

            # Check error response
            if response.status_code == 404:
                return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

            # Try to parse error from response
            try:
                data = response.json()
                error = data.get("chart", {}).get("error")
                if error and "No data found" in str(error):
                    return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)
            except Exception:
                pass

            return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

        except requests.RequestException as e:
            logger.warning(f"Yahoo Finance API check failed: {e}")
            return None

    def _check_nasdaq_ipo_calendar(self) -> Optional[IPOInfo]:
        """Check NASDAQ IPO calendar for upcoming/recent IPOs."""
        try:
            url = "https://api.nasdaq.com/api/ipo/calendar"
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            }
            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()

                # Search in upcoming, priced, and filed sections
                for section in ["upcoming", "priced", "filed"]:
                    rows = data.get("data", {}).get(section, {}).get("rows", []) or []
                    for row in rows:
                        symbol = (row.get("proposedTickerSymbol") or "").upper()
                        if symbol == self.symbol:
                            company_name = row.get("companyName")
                            expected_date = row.get("expectedPriceDate") or row.get("pricedDate")

                            if section == "priced":
                                status = IPOStatus.SUBSCRIPTION_CLOSED
                            elif section == "upcoming":
                                status = IPOStatus.SUBSCRIPTION_OPEN
                            else:
                                status = IPOStatus.UPCOMING

                            return IPOInfo(
                                symbol=self.symbol,
                                status=status,
                                company_name=company_name,
                                exchange="NASDAQ",
                                listing_date=expected_date,
                                details=f"Found in NASDAQ {section} IPOs",
                            )

            return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

        except requests.RequestException as e:
            logger.warning(f"NASDAQ calendar check failed: {e}")
            return None


def check_ipo_status(symbol: str) -> IPOInfo:
    """Convenience function to check IPO status."""
    checker = IPOChecker(symbol)
    return checker.check_status()
