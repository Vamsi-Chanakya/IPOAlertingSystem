"""Multi-source IPO data fetcher.

Aggregates upcoming IPO data from multiple sources:
- NASDAQ IPO Calendar API
- Yahoo Finance IPO Calendar
- IPOScoop
- MarketWatch
- Webull
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class IPOData:
    """Unified IPO data from any source."""
    symbol: str
    company_name: Optional[str] = None
    expected_date: Optional[datetime] = None
    price_range: Optional[str] = None
    exchange: Optional[str] = None
    shares: Optional[str] = None
    sources: Set[str] = field(default_factory=set)

    def days_until(self, today: datetime.date = None) -> Optional[int]:
        if today is None:
            today = datetime.now().date()
        if self.expected_date:
            return (self.expected_date.date() - today).days
        return None

    def format_date(self) -> str:
        if self.expected_date:
            return self.expected_date.strftime("%Y-%m-%d")
        return "TBD"


class IPODataFetcher:
    """Fetch IPO data from multiple sources."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def fetch_all_sources(self, max_days_ahead: int = 7) -> List[IPOData]:
        """Fetch IPOs from all sources and return unified list."""
        all_ipos: Dict[str, IPOData] = {}
        today = datetime.now().date()

        # Fetch from each source
        sources = [
            ("NASDAQ", self._fetch_nasdaq),
            ("Yahoo Finance", self._fetch_yahoo_finance),
            ("IPOScoop", self._fetch_iposcoop),
            ("MarketWatch", self._fetch_marketwatch),
            ("Webull", self._fetch_webull),
        ]

        for source_name, fetch_func in sources:
            try:
                logger.info(f"Fetching from {source_name}...")
                ipos = fetch_func()
                for ipo in ipos:
                    self._merge_ipo(all_ipos, ipo, source_name)
                logger.info(f"  Found {len(ipos)} IPOs from {source_name}")
            except Exception as e:
                logger.warning(f"  Failed to fetch from {source_name}: {e}")

        # Filter by date range and return
        valid_ipos = []
        for symbol, ipo in all_ipos.items():
            days = ipo.days_until(today)
            if days is not None and 0 <= days <= max_days_ahead:
                valid_ipos.append(ipo)
                logger.info(f"  Valid: {ipo.symbol} ({ipo.company_name}) - {ipo.format_date()} ({days} days) [Sources: {', '.join(ipo.sources)}]")

        logger.info(f"Total valid IPOs within {max_days_ahead} days: {len(valid_ipos)}")
        return valid_ipos

    def _merge_ipo(self, all_ipos: Dict[str, IPOData], new_ipo: IPOData, source: str):
        """Merge IPO data, preferring more complete information."""
        symbol = new_ipo.symbol.upper()
        new_ipo.sources.add(source)

        if symbol not in all_ipos:
            all_ipos[symbol] = new_ipo
            return

        existing = all_ipos[symbol]
        existing.sources.add(source)

        # Merge fields, preferring non-None values
        if new_ipo.company_name and not existing.company_name:
            existing.company_name = new_ipo.company_name
        if new_ipo.expected_date and not existing.expected_date:
            existing.expected_date = new_ipo.expected_date
        if new_ipo.price_range and not existing.price_range:
            existing.price_range = new_ipo.price_range
        if new_ipo.exchange and not existing.exchange:
            existing.exchange = new_ipo.exchange
        if new_ipo.shares and not existing.shares:
            existing.shares = new_ipo.shares

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try multiple date formats."""
        if not date_str:
            return None

        date_str = date_str.strip()
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y/%m/%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try to extract date from strings like "Jan 22" (assume current year)
        try:
            month_day = datetime.strptime(date_str, "%b %d")
            return month_day.replace(year=datetime.now().year)
        except ValueError:
            pass

        return None

    def _fetch_nasdaq(self) -> List[IPOData]:
        """Fetch from NASDAQ IPO Calendar API."""
        results = []
        try:
            url = "https://api.nasdaq.com/api/ipo/calendar"
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            }
            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()

                for section in ["upcoming", "priced", "filed"]:
                    rows = data.get("data", {}).get(section, {}).get("rows", []) or []
                    for row in rows:
                        symbol = (row.get("proposedTickerSymbol") or "").upper()
                        if not symbol:
                            continue

                        date_str = row.get("expectedPriceDate") or row.get("pricedDate")
                        expected_date = self._parse_date(date_str)

                        results.append(IPOData(
                            symbol=symbol,
                            company_name=row.get("companyName"),
                            expected_date=expected_date,
                            price_range=row.get("proposedSharePrice"),
                            exchange="NASDAQ",
                            shares=row.get("sharesOffered"),
                        ))

        except requests.RequestException as e:
            logger.warning(f"NASDAQ API error: {e}")

        return results

    def _fetch_yahoo_finance(self) -> List[IPOData]:
        """Fetch from Yahoo Finance IPO Calendar."""
        results = []
        try:
            # Yahoo Finance IPO calendar
            url = "https://finance.yahoo.com/calendar/ipo"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Find IPO table rows
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")[1:]  # Skip header
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 4:
                            symbol = cols[0].get_text(strip=True).upper()
                            company = cols[1].get_text(strip=True)
                            exchange = cols[2].get_text(strip=True)
                            date_str = cols[3].get_text(strip=True)
                            price_range = cols[4].get_text(strip=True) if len(cols) > 4 else None

                            if symbol:
                                results.append(IPOData(
                                    symbol=symbol,
                                    company_name=company,
                                    expected_date=self._parse_date(date_str),
                                    exchange=exchange,
                                    price_range=price_range,
                                ))

        except requests.RequestException as e:
            logger.warning(f"Yahoo Finance error: {e}")

        return results

    def _fetch_iposcoop(self) -> List[IPOData]:
        """Fetch from IPOScoop."""
        results = []
        try:
            url = "https://www.iposcoop.com/ipo-calendar/"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Find IPO entries
                tables = soup.find_all("table")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 3:
                            # IPOScoop format varies, try to extract data
                            text = row.get_text(" ", strip=True)

                            # Look for ticker symbol pattern
                            symbol_match = re.search(r'\b([A-Z]{2,5})\b', text)
                            if symbol_match:
                                symbol = symbol_match.group(1)

                                # Try to find date
                                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
                                expected_date = None
                                if date_match:
                                    expected_date = self._parse_date(date_match.group(1))

                                # Try to find price range
                                price_match = re.search(r'\$[\d.]+-\$[\d.]+|\$[\d.]+', text)
                                price_range = price_match.group(0) if price_match else None

                                # Get company name from first column
                                company_name = cols[0].get_text(strip=True) if cols else None

                                if symbol and len(symbol) <= 5:
                                    results.append(IPOData(
                                        symbol=symbol,
                                        company_name=company_name,
                                        expected_date=expected_date,
                                        price_range=price_range,
                                    ))

        except requests.RequestException as e:
            logger.warning(f"IPOScoop error: {e}")

        return results

    def _fetch_marketwatch(self) -> List[IPOData]:
        """Fetch from MarketWatch IPO Calendar."""
        results = []
        try:
            url = "https://www.marketwatch.com/tools/ipo-calendar"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Find IPO table
                table = soup.find("table", class_="table--primary")
                if table:
                    rows = table.find_all("tr")[1:]  # Skip header
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 4:
                            company = cols[0].get_text(strip=True)
                            symbol = cols[1].get_text(strip=True).upper()
                            date_str = cols[2].get_text(strip=True)
                            price_range = cols[3].get_text(strip=True) if len(cols) > 3 else None

                            if symbol:
                                results.append(IPOData(
                                    symbol=symbol,
                                    company_name=company,
                                    expected_date=self._parse_date(date_str),
                                    price_range=price_range,
                                ))

        except requests.RequestException as e:
            logger.warning(f"MarketWatch error: {e}")

        return results

    def _fetch_webull(self) -> List[IPOData]:
        """Fetch from Webull IPO Calendar API."""
        results = []
        try:
            # Webull uses an API endpoint
            url = "https://quotes-gw.webullfintech.com/api/ipo/listIpo"
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            }
            params = {
                "regionId": 6,  # US market
                "status": 1,    # Upcoming
                "pageSize": 50,
            }
            response = self.session.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                items = data.get("data", []) or []

                for item in items:
                    symbol = (item.get("tickerSymbol") or item.get("symbol") or "").upper()
                    if not symbol:
                        continue

                    # Parse expected date
                    expected_date = None
                    date_str = item.get("expectedListDate") or item.get("ipoDate")
                    if date_str:
                        expected_date = self._parse_date(date_str)

                    # Parse price range
                    price_low = item.get("ipoPriceLow")
                    price_high = item.get("ipoPriceHigh")
                    price_range = None
                    if price_low and price_high:
                        price_range = f"${price_low}-${price_high}"
                    elif item.get("ipoPrice"):
                        price_range = f"${item.get('ipoPrice')}"

                    results.append(IPOData(
                        symbol=symbol,
                        company_name=item.get("name") or item.get("companyName"),
                        expected_date=expected_date,
                        price_range=price_range,
                        exchange=item.get("exchangeCode"),
                        shares=item.get("sharesOffered"),
                    ))

        except requests.RequestException as e:
            logger.warning(f"Webull error: {e}")

        return results


def fetch_upcoming_ipos(max_days_ahead: int = 7) -> List[IPOData]:
    """Convenience function to fetch IPOs from all sources."""
    fetcher = IPODataFetcher()
    return fetcher.fetch_all_sources(max_days_ahead)
