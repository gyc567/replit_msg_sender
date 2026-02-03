"""Tests for arkm.py - Arkham Intelligence monitoring."""
import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import once at module level
import arkm


@pytest.fixture(autouse=True)
def reset_arkm_state():
    """Reset module state before each test."""
    arkm.processed_txs = set()
    yield
    arkm.processed_txs = set()


class TestArkhamConfig:
    """Test configuration loading."""

    def test_config_loads_from_env(self):
        """Verify configuration loads from environment variables."""
        assert arkm.BOT_TOKEN == 'test_bot_token'
        assert arkm.TG_CHAT_ID == 'test_chat_id'
        assert arkm.ARKHAM_API_KEY == 'test_arkham_key'

    def test_default_values(self):
        """Test default configuration values."""
        assert arkm.ARKHAM_BASE_URL == 'https://api.arkhamintelligence.com'
        assert arkm.MIN_VALUE_USD == 1000000
        assert isinstance(arkm.TARGET_ENTITIES, list)

    def test_target_entities_parsed(self):
        """Test that target entities are parsed from comma-separated string."""
        assert 'binance' in arkm.TARGET_ENTITIES
        assert 'blackrock' in arkm.TARGET_ENTITIES


class TestArkhamAPI:
    """Test Arkham API interactions."""

    @patch('arkm.requests.get')
    def test_get_transfers_success(self, mock_get):
        """Test successful transfer retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'transfers': [
                {
                    'transactionHash': '0x123',
                    'tokenSymbol': 'BTC',
                    'unitValue': 1.5,
                    'historicalUSD': 50000,
                    'blockTimestamp': '2024-01-01T00:00:00Z',
                    'fromAddress': {'address': '0xsender'},
                    'toAddress': {'address': '0xreceiver'}
                }
            ]
        }
        mock_get.return_value = mock_response

        transfers = arkm.get_arkham_transfers('binance')

        assert transfers is not None
        assert len(transfers) == 1
        assert transfers[0]['transactionHash'] == '0x123'

    @patch('arkm.requests.get')
    def test_get_transfers_empty(self, mock_get):
        """Test empty transfer list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'transfers': []}
        mock_get.return_value = mock_response

        transfers = arkm.get_arkham_transfers('binance')
        assert transfers == []

    @patch('arkm.requests.get')
    def test_get_transfers_api_error(self, mock_get):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        transfers = arkm.get_arkham_transfers('binance')
        assert transfers == []


class TestTelegramSending:
    """Test Telegram message sending."""

    @patch('arkm.requests.post')
    def test_send_telegram_success(self, mock_post):
        """Test successful Telegram message send."""
        mock_response = Mock()
        mock_response.json.return_value = {'ok': True}
        mock_post.return_value = mock_response

        arkm.send_tg('Test message')

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'test_bot_token' in call_args[0][0]

    @patch('arkm.requests.post')
    def test_send_telegram_topic_fallback(self, mock_post):
        """Test automatic fallback when topic ID is invalid."""
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            'ok': False,
            'description': 'message thread not found'
        }

        mock_response2 = Mock()
        mock_response2.json.return_value = {'ok': True}

        mock_post.side_effect = [mock_response1, mock_response2]

        arkm.send_tg('Test message')

        assert mock_post.call_count == 2


class TestDeduplication:
    """Test transaction deduplication."""

    def test_deduplication(self):
        """Test that duplicate transactions are filtered."""
        tx_hash = '0xduplicate'
        arkm.processed_txs.add(tx_hash)

        assert tx_hash in arkm.processed_txs
        assert '0xnew' not in arkm.processed_txs


class TestLogFunction:
    """Test logging functionality."""

    def test_log_output(self):
        """Test that log function produces output."""
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        arkm.log('Test message')

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        assert 'Test message' in output
        assert '[' in output


class TestCommonHeaders:
    """Test common headers configuration."""

    def test_common_headers_defined(self):
        """Test that common headers are defined."""
        assert 'User-Agent' in arkm.COMMON_HEADERS
        assert 'Accept' in arkm.COMMON_HEADERS
        assert 'Accept-Language' in arkm.COMMON_HEADERS
