"""IPO status checking module."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from bs4 import BeautifulSoup

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
        # Try different sources in order of reliability
        info = self._check_yahoo_finance()
        if info and info.status != IPOStatus.NOT_FOUND:
            return info

        info = self._check_nasdaq_ipo_calendar()
        if info and info.status != IPOStatus.NOT_FOUND:
            return info

        info = self._check_marketwatch()
        if info and info.status != IPOStatus.NOT_FOUND:
            return info

        # Return not found status
        return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

    def _check_yahoo_finance(self) -> Optional[IPOInfo]:
        """Check Yahoo Finance for stock listing status."""
        try:
            url = f"https://finance.yahoo.com/quote/{self.symbol}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Check if the stock page exists and has price data
                price_element = soup.find("fin-streamer", {"data-field": "regularMarketPrice"})
                if price_element:
                    price = price_element.get("data-value") or price_element.text.strip()

                    # Get company name
                    title_element = soup.find("h1")
                    company_name = None
                    if title_element:
                        company_name = title_element.text.strip()

                    # Get exchange info
                    exchange_element = soup.find("span", class_=lambda x: x and "exchange" in x.lower() if x else False)
                    exchange = exchange_element.text.strip() if exchange_element else None

                    return IPOInfo(
                        symbol=self.symbol,
                        status=IPOStatus.TRADING,
                        company_name=company_name,
                        exchange=exchange,
                        price=price,
                        details=f"Currently trading at ${price}",
                    )

            return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

        except requests.RequestException as e:
            logger.warning(f"Yahoo Finance check failed: {e}")
            return None

    def _check_nasdaq_ipo_calendar(self) -> Optional[IPOInfo]:
        """Check NASDAQ IPO calendar for upcoming/recent IPOs."""
        try:
            # Check upcoming IPOs
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
                    rows = data.get("data", {}).get(section, {}).get("rows", [])
                    for row in rows:
                        symbol = row.get("proposedTickerSymbol", "").upper()
                        if symbol == self.symbol:
                            company_name = row.get("companyName")
                            expected_date = row.get("expectedPriceDate") or row.get("pricedDate")

                            if section == "priced":
                                status = IPOStatus.SUBSCRIPTION_CLOSED
                            elif section == "upcoming":
                                status = IPOStatus.UPCOMING
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

    def _check_marketwatch(self) -> Optional[IPOInfo]:
        """Check MarketWatch for stock information."""
        try:
            url = f"https://www.marketwatch.com/investing/stock/{self.symbol.lower()}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Check for price element
                price_element = soup.find("bg-quote", class_="value")
                if price_element:
                    price = price_element.text.strip()

                    # Get company name
                    name_element = soup.find("h1", class_="company__name")
                    company_name = name_element.text.strip() if name_element else None

                    return IPOInfo(
                        symbol=self.symbol,
                        status=IPOStatus.TRADING,
                        company_name=company_name,
                        price=price,
                        details=f"Trading on MarketWatch at ${price}",
                    )

            return IPOInfo(symbol=self.symbol, status=IPOStatus.NOT_FOUND)

        except requests.RequestException as e:
            logger.warning(f"MarketWatch check failed: {e}")
            return None


def check_ipo_status(symbol: str) -> IPOInfo:
    """Convenience function to check IPO status."""
    checker = IPOChecker(symbol)
    return checker.check_status()
