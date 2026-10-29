# Hyperliquid Grid Trading Bot

A Python-based experimental grid trading bot for the [Hyperliquid](https://hyperliquid.xyz/) perpetual futures exchange. It combines configurable grid orders, exchange event monitoring, take-profit adjustments, and Telegram-based control.

## Features

- Configurable grid parameters: trading pair, deposit, leverage, order spacing, number of orders, and martingale sizing factor
- Market entry followed by a batch of limit orders
- Take-profit price recalculation as grid orders fill
- WebSocket user-event handling, with a reconnection watchdog and state synchronization attempts
- Separate worker threads and event queues for individual trading bots
- Telegram commands, notifications, and application logging
- Exchange-specific order size and price rounding

## Project structure

| File | Purpose |
| --- | --- |
| `hyperliquid_bot.py` | Application entry point |
| `main_handler.py` | Bot orchestration and WebSocket connection management |
| `grid_bot_module.py` | Grid strategy, orders, and take-profit logic |
| `telegram.py` | Telegram commands and notifications |
| `setup_api.py` | Exchange authentication and account setup |
| `logger_module.py` | Logging configuration |
| `configs/*.yaml` | Per-bot strategy parameters |

## Setup

This is a development project, **not a production-ready trading system**. Review and test the code before connecting an account with funds. Trading leveraged perpetual futures can result in substantial losses or liquidation.

1. Clone the repository and install the Python dependencies used by the code: `hyperliquid-python-sdk`, `pyTelegramBotAPI`, `numpy`, `PyYAML`, and `eth-account`.
2. Create a local `config.json` in the project root with `account_address`, `secret_key`, and `keystore_path` fields. The implementation accepts a raw private key or prompts for the password of a local encrypted keystore. **Never commit credentials or private keys to GitHub.**
3. Create a local `tg_config.json` containing `tg_secret` (Telegram bot token) and `chat_id` (destination chat ID). Keep this file private.
4. Review the example strategy file `configs/ETH_L.yaml` and adjust the parameters to your own test setup.
5. Start the application:

```bash
python hyperliquid_bot.py
```

The application currently targets the Hyperliquid **mainnet**. Running it does not automatically start a trading grid; use the Telegram controller to add one.

## Telegram commands

| Command | Action |
| --- | --- |
| `add ETH_L` | Start a tracker using `configs/ETH_L.yaml` |
| `remove ETH_L` | Request a tracker stop |
| `terminate ETH_L` | Request a stop and cancel its orders |
| `exclude ETH_L` | Remove a tracker from the handler |
| `ping` | Check Telegram command responsiveness |
| `log` | Request the log file |

**Important limitations:** The current grid price calculation implements the buy-side path; the sell-side branch is incomplete. Telegram command handling does not validate the sender, and stopping or restarting workers should not be treated as a guaranteed safe shutdown. WebSocket reconnection and order-state recovery are best-effort, not a substitute for risk controls. Do not operate this version unattended with real funds.

## Tech stack

**Python**, Hyperliquid Python SDK, WebSockets, threading and queues, NumPy, YAML, Telegram Bot API.

*Personal software development project for exploring exchange APIs, asynchronous event processing, and automated trading strategies.*
