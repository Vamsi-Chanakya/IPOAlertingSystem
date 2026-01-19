# IPO Alerting System - Project Documentation

## Overview
A GitHub Actions-based monitoring system that checks BITGO IPO availability every 5 minutes and sends Telegram alerts when shares become available for trading.

## Project Structure
```
IPOAlertingSystem/
├── .github/workflows/ipo_monitor.yml  # GitHub Action workflow (every 5 mins)
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration from environment variables
│   ├── ipo_checker.py         # IPO status checking (Yahoo Finance, NASDAQ, MarketWatch)
│   └── telegram_notifier.py   # Telegram Bot API integration
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
└── ipo_state.json            # State tracking (auto-generated)
```

## Key Components

### IPO Checker (`src/ipo_checker.py`)
- Checks multiple sources: Yahoo Finance, NASDAQ IPO Calendar, MarketWatch
- Returns structured `IPOInfo` with status, price, exchange info
- Status types: NOT_FOUND, UPCOMING, SUBSCRIPTION_OPEN, SUBSCRIPTION_CLOSED, ALLOTMENT_PENDING, ALLOTMENT_DONE, LISTED, TRADING

### Telegram Notifier (`src/telegram_notifier.py`)
- Sends formatted HTML messages via Telegram Bot API
- Includes emoji indicators for different statuses
- Error handling for API failures

### State Management
- Uses `ipo_state.json` to track previous status
- Only sends alerts on status changes
- Cached between GitHub Actions runs

## Commands

### Run locally
```bash
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export IPO_SYMBOL="BITGO"  # optional, defaults to BITGO
python main.py
```

### Install dependencies
```bash
pip install -r requirements.txt
```

## Required Secrets (GitHub)
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

## Alert Conditions
Sends notification when:
- IPO subscription opens
- Allotment results are out
- Shares become available for trading (listing day)
