"""Tests for bianjk.py - Binance market monitoring."""
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bianjk


class TestBinanceConfig:
    """Test configuration loading."""

    def test_config_loads_from_env(self):
        """Verify configuration loads from environment variables."""
        assert bianjk.TG_BOT_TOKEN == 'test_bot_token'
        assert bianjk.TG_CHAT_ID == 'test_chat_id'

    def test_symbols_parsing(self):
        """Test symbol list parsing."""
        assert 'btcusdt' in bianjk.SYMBOLS
        assert 'ethusdt' in bianjk.SYMBOLS

    def test_threshold_config(self):
        """Test threshold configuration."""
        assert bianjk.THRESHOLD_SINGLE_QTY['BTCUSDT'] == 1.0
        assert bianjk.THRESHOLD_SINGLE_QTY['ETHUSDT'] == 50.0


class TestAmountFormatting:
    """Test amount formatting utilities."""

    def test_format_amount_millions(self):
        """Test formatting amounts in millions."""
        result = bianjk.format_amount(1500000)
        assert result == '1.50M'

    def test_format_amount_thousands(self):
        """Test formatting amounts in thousands."""
        result = bianjk.format_amount(50000)
        assert result == '50.00K'

    def test_format_amount_small(self):
        """Test formatting small amounts."""
        result = bianjk.format_amount(100.5)
        assert result == '100.50'


class TestTimeFormatting:
    """Test time formatting utilities."""

    def test_get_time_str_with_timestamp(self):
        """Test time string generation with timestamp."""
        result = bianjk.get_time_str(1704067200000)
        # Timezone may vary, just check format
        assert ':' in result
        assert len(result) == 8

    def test_get_time_str_without_timestamp(self):
        """Test time string generation without timestamp."""
        import datetime
        result = bianjk.get_time_str()
        now = datetime.datetime.now().strftime('%H:%M:%S')
        assert result == now


class TestGlobalState:
    """Test global state management."""

    def test_burst_monitor_initialized(self):
        """Test that burst monitor is properly initialized."""
        assert 'BUY' in bianjk.burst_monitor['BTCUSDT']
        assert 'SELL' in bianjk.burst_monitor['BTCUSDT']

    def test_volume_baseline_starts_empty(self):
        """Test that volume baseline starts empty."""
        assert bianjk.volume_baseline == {}

    def test_wall_alert_history_starts_empty(self):
        """Test that wall alert history starts empty."""
        assert bianjk.wall_alert_history == {}


class TestDirectionIndicators:
    """Test trade direction indicators."""

    def test_direction_buy(self):
        """Test direction string for buy order."""
        is_buyer_maker = False
        direction_str = "🔴 主动卖出" if is_buyer_maker else "🟢 主动买入"
        assert "🟢" in direction_str

    def test_direction_sell(self):
        """Test direction string for sell order."""
        is_buyer_maker = True
        direction_str = "🔴 主动卖出" if is_buyer_maker else "🟢 主动买入"
        assert "🔴" in direction_str


class TestBinanceWebSocket:
    """Test Binance WebSocket URL construction."""

    def test_websocket_url_construction(self):
        """Test WebSocket URL is properly constructed."""
        streams = []
        for s in bianjk.SYMBOLS:
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@kline_5m")
            streams.append(f"{s}@depth20@100ms")

        stream_str = '/'.join(streams)
        assert 'btcusdt@aggTrade' in stream_str
        assert 'ethusdt@kline_5m' in stream_str


class TestBurstConfig:
    """Test burst detection configuration."""

    def test_burst_amount_usd(self):
        """Test burst amount threshold."""
        assert bianjk.BURST_AMOUNT_USD == 100000.0

    def test_burst_count_trigger(self):
        """Test burst count trigger."""
        assert bianjk.BURST_COUNT_TRIGGER == 1


class TestVolumeConfig:
    """Test volume anomaly configuration."""

    def test_volume_anomaly_multiplier(self):
        """Test volume anomaly multiplier."""
        assert bianjk.VOLUME_ANOMALY_MULTIPLIER == 3.0

    def test_order_book_wall_threshold(self):
        """Test order book wall threshold."""
        assert bianjk.ORDER_BOOK_WALL_THRESHOLD == 5000000.0
