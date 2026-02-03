# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A cryptocurrency monitoring and alerting system that tracks multiple data sources (Arkham Intelligence, Binance, Mlion News) and sends real-time alerts to a Telegram group.

## Commands

```bash
# Run all monitors via orchestrator
python main.py

# Run individual monitors
python arkm.py      # Arkham Intelligence transfers
python bianjk.py    # Binance market monitoring
python zixun.py     # Mlion news flash
python botsever.py  # Webhook server (requires ngrok for external access)
```

## Architecture

**Orchestration Pattern**: `main.py` launches all monitors as separate subprocesses and implements a守护模式 (watchdog loop) that restarts any crashed processes every 10 seconds. `botsever.py` runs in a thread instead of subprocess to avoid port conflicts.

**Data Flow**: Each monitor script follows the pattern: fetch data → deduplicate → format message → send to Telegram.

**Key Components**:

| File | Purpose | Data Source |
|------|---------|-------------|
| `main.py` | Process orchestrator + watchdog | - |
| `arkm.py` | Tracks large transfers (>$1M) from entities | Arkham API / 2-min interval |
| `bianjk.py` | Real-time market monitoring via WebSocket | Binance WS / real-time |
| `zixun.py` | Crypto news flash monitoring | Mlion API / 60-sec interval |
| `botsever.py` | Flask HTTP server for Twitter webhooks | HTTP POST |

**Deduplication**: Each script maintains an in-memory set (`processed_txs`, etc.) to prevent duplicate alerts. Large sets are cleared periodically.

**State Persistence**: `zixun.py` uses `.zixun_state.json` to track the last news fingerprint across restarts.

## Configuration

All configuration is managed via `.env` file. Key environment variables:

**Secrets:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram group ID
- `ARKHAM_API_KEY` - Arkham Intelligence API key
- `MLION_API_KEY` - Mlion AI API key

**Thresholds:**
- `ARKHAM_MIN_VALUE_USD` - Minimum USD value for Arkham alerts (default: 1000000)
- `BINANCE_BTC_THRESHOLD` - BTC quantity threshold (default: 1.0)
- `BINANCE_ETH_THRESHOLD` - ETH quantity threshold (default: 50.0)
- `BINANCE_BURST_AMOUNT_USD` - Burst detection threshold (default: 100000)
- `BINANCE_VOLUME_ANOMALY_MULTIPLIER` - Volume anomaly multiplier (default: 3.0)
- `BINANCE_ORDER_BOOK_WALL_THRESHOLD` - Order book wall threshold (default: 5000000)

**Topic IDs (per script):**
- `ARKHAM_TOPIC_ID` - Arkham alerts topic (default: 1)
- `BINANCE_TOPIC_ID` - Binance alerts topic (default: 3)
- `ZIXUN_TOPIC_ID` - News alerts topic (default: 4)
- `BOTSEVER_TOPIC_ID` - Webhook alerts topic (default: 13)

## Telegram Integration Pattern

All scripts follow the same error-handling pattern for topic ID issues:
```python
# Auto-fallback if topic thread not found
if not result.get("ok") and "message thread not found" in description:
    payload.pop("message_thread_id", None)
    retry_request()
```

## Binance Monitoring Logic

`bianjk.py` monitors four signals via WebSocket:
1. **Single large trades**: BTC >= 1.0, ETH >= 50.0
2. **1-minute burst**: $100K+ in <1 min window
3. **Volume anomaly**: 3x the 5-minute average
4. **Order book walls**: >= $5M bid/ask

## Webhook Server

`botsever.py` runs on an auto-selected port starting at 5006. Use ngrok for external access:
```bash
ngrok http <port>
```
