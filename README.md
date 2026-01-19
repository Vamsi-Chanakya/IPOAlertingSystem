# IPO Alerting System

A GitHub Actions-based monitoring system that checks IPO availability and sends Telegram alerts when shares become available for trading.

## Features

- Monitors IPO status every 5 minutes via GitHub Actions
- Checks multiple data sources (Yahoo Finance, NASDAQ, MarketWatch)
- Sends Telegram notifications on status changes
- Tracks state between runs to avoid duplicate alerts
- Configurable IPO symbol to monitor

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. Message your new bot (send any message)
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":XXXXXXXX}` - that's your chat ID

### 3. Configure GitHub Secrets

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your chat ID |

### 4. (Optional) Configure IPO Symbol

By default, the system monitors `BITGO`. To change this:

1. Go to **Settings > Secrets and variables > Actions > Variables**
2. Add a variable named `IPO_SYMBOL` with your desired symbol

### 5. Enable GitHub Actions

1. Push this repository to GitHub
2. Go to **Actions** tab
3. Enable workflows if prompted
4. The monitor will run automatically every 5 minutes

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd IPOAlertingSystem

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export IPO_SYMBOL="BITGO"  # optional

# Run the checker
python main.py
```

## Project Structure

```
IPOAlertingSystem/
├── .github/
│   └── workflows/
│       └── ipo_monitor.yml      # GitHub Action (runs every 5 mins)
├── src/
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── ipo_checker.py           # IPO status checking logic
│   └── telegram_notifier.py     # Telegram notification module
├── main.py                       # Entry point
├── requirements.txt              # Python dependencies
├── CLAUDE.md                     # Project documentation
└── README.md                     # This file
```

## Data Sources

The system checks these sources for IPO information:

1. **Yahoo Finance** - Real-time stock data for listed securities
2. **NASDAQ IPO Calendar** - Upcoming and recently priced IPOs
3. **MarketWatch** - Stock quotes and company information

## Alert Types

You'll receive notifications when:

- IPO subscription opens
- Allotment results are announced
- **Shares become available for trading** (listing day)

## Troubleshooting

### No alerts received

1. Check that GitHub Actions is enabled
2. Verify secrets are correctly set
3. Check the Actions tab for any workflow errors
4. Ensure your bot is not blocked

### Workflow not running

- GitHub Actions cron jobs may have delays of up to 15 minutes
- Ensure the repository has recent activity (workflows pause after 60 days of inactivity)

## License

MIT
