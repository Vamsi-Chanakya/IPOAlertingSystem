"""Volatility checking module - alerts on sudden price movements."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Alert threshold - percentage change to trigger alert
VOLATILITY_THRESHOLD_PERCENT = 5.0


class MovementType(Enum):
    """Type of price movement."""

    NONE = "none"
    RALLY = "rally"
    DROP = "drop"


@dataclass
class VolatilityInfo:
    """Volatility information data class."""

    symbol: str
    current_price: Optional[float] = None
    previous_price: Optional[float] = None
    change_percent: Optional[float] = None
    movement: MovementType = MovementType.NONE
    company_name: Optional[str] = None
    currency: str = "USD"
    error: Optional[str] = None

    def has_significant_movement(self) -> bool:
        """Check if there's a significant price movement."""
        return self.movement in (MovementType.RALLY, MovementType.DROP)


class VolatilityChecker:
    """Check price volatility for stocks and crypto."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def check_volatility(self, previous_price: Optional[float] = None) -> VolatilityInfo:
        """Check current price and compare with previous price."""
        # Get current price from Yahoo Finance API
        price_info = self._get_current_price()

        if price_info.error:
            return price_info

        if previous_price is None or price_info.current_price is None:
            # First run or no price - return current info without movement
            return price_info

        # Calculate percentage change
        price_info.previous_price = previous_price
        change = price_info.current_price - previous_price
        change_percent = (change / previous_price) * 100
        price_info.change_percent = round(change_percent, 2)

        # Determine movement type
        if change_percent >= VOLATILITY_THRESHOLD_PERCENT:
            price_info.movement = MovementType.RALLY
        elif change_percent <= -VOLATILITY_THRESHOLD_PERCENT:
            price_info.movement = MovementType.DROP

        return price_info

    def _get_current_price(self) -> VolatilityInfo:
        """Get current price from Yahoo Finance API."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self.symbol}"
            params = {"interval": "1d", "range": "1d"}
            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result")

                if result and len(result) > 0:
                    meta = result[0].get("meta", {})

                    symbol = meta.get("symbol", "").upper()
                    if symbol != self.symbol:
                        return VolatilityInfo(
                            symbol=self.symbol,
                            error=f"Symbol mismatch: expected {self.symbol}, got {symbol}",
                        )

                    price = meta.get("regularMarketPrice")
                    company_name = meta.get("shortName") or meta.get("longName")
                    currency = meta.get("currency", "USD")

                    if price:
                        return VolatilityInfo(
                            symbol=self.symbol,
                            current_price=price,
                            company_name=company_name,
                            currency=currency,
                        )

            # Handle error response
            try:
                data = response.json()
                error = data.get("chart", {}).get("error", {})
                error_desc = error.get("description", "Unknown error")
                return VolatilityInfo(symbol=self.symbol, error=error_desc)
            except Exception:
                pass

            return VolatilityInfo(symbol=self.symbol, error="Failed to fetch price data")

        except requests.RequestException as e:
            logger.warning(f"Yahoo Finance API check failed for {self.symbol}: {e}")
            return VolatilityInfo(symbol=self.symbol, error=str(e))


def check_volatility(symbol: str, previous_price: Optional[float] = None) -> VolatilityInfo:
    """Convenience function to check volatility."""
    checker = VolatilityChecker(symbol)
    return checker.check_volatility(previous_price)
