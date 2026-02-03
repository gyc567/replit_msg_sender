"""Tests for zixun.py - Mlion news monitoring."""
import os
import sys
import pytest
import json
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zixun


class TestZixunConfig:
    """Test configuration loading."""

    def test_config_loads_from_env(self):
        """Verify configuration loads from environment variables."""
        assert zixun.BOT_TOKEN == 'test_bot_token'
        assert zixun.CHAT_ID == 'test_chat_id'
        assert zixun.MLION_API_KEY == 'test_mlion_key'

    def test_default_api_url(self):
        """Test default API URL."""
        assert zixun.API_URL == 'https://api.mlion.ai/v1/news/flash'

    def test_default_topic_id(self):
        """Test default topic ID."""
        assert zixun.TOPIC_ID == 4


class TestNewsFetching:
    """Test news fetching functionality."""

    @patch('zixun.requests.get')
    def test_get_latest_news_success(self, mock_get):
        """Test successful news retrieval."""
        # Reset fingerprint to simulate first run
        zixun.last_news_fingerprint = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 'news_123',
                'title': 'Test News Title',
                'content': 'Test content',
                'pub_time': '2024-01-01T12:00:00Z',
                'tags': ['crypto', 'bitcoin'],
                'url': 'https://example.com/news/123'
            }
        ]
        mock_get.return_value = mock_response

        news = zixun.get_latest_news()

        assert news is not None
        assert news['title'] == 'Test News Title'

    @patch('zixun.requests.get')
    def test_get_latest_news_empty(self, mock_get):
        """Test empty news list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        news = zixun.get_latest_news()
        assert news is None


class TestDeduplication:
    """Test news deduplication functionality."""

    def test_duplicate_news_skipped(self):
        """Test that duplicate news is skipped."""
        zixun.last_news_fingerprint = 'news_123'

        news = {'id': 'news_123', 'title': 'Duplicate News'}
        fingerprint = news.get('id')

        is_new = fingerprint != zixun.last_news_fingerprint
        assert is_new is False


class TestStateManagement:
    """Test state file management."""

    def test_load_last_fingerprint_exists(self):
        """Test loading fingerprint from existing file."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'last_fingerprint': 'test_fingerprint'}, f)
            temp_file = f.name

        try:
            zixun.STATE_FILE = temp_file
            result = zixun.load_last_fingerprint()
            assert result == 'test_fingerprint'
        finally:
            os.unlink(temp_file)

    def test_save_last_fingerprint(self):
        """Test saving fingerprint to file."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, 'state.json')
            zixun.STATE_FILE = temp_file

            zixun.save_last_fingerprint('new_fingerprint')

            with open(temp_file, 'r') as f:
                data = json.load(f)
                assert data['last_fingerprint'] == 'new_fingerprint'


class TestMessageFormatting:
    """Test message formatting functionality."""

    def test_format_message_complete(self):
        """Test formatting a complete news message."""
        news = {
            'title': 'Bitcoin Reaches New High',
            'content': 'Bitcoin has surpassed $50,000 for the first time.',
            'pub_time': '2024-01-01T12:00:00Z',
            'tags': ['bitcoin', 'crypto'],
            'url': 'https://example.com/news/123'
        }

        msg = zixun.format_message(news)

        assert msg is not None
        assert 'Bitcoin Reaches New High' in msg
        assert 'https://example.com/news/123' in msg

    def test_format_message_empty(self):
        """Test formatting empty message."""
        result = zixun.format_message(None)
        assert result is None


class TestTelegramSending:
    """Test Telegram message sending."""

    @patch('zixun.requests.post')
    def test_send_telegram_success(self, mock_post):
        """Test successful Telegram message send."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'ok': True}
        mock_post.return_value = mock_response

        zixun.send_telegram_message('Test message')

        mock_post.assert_called_once()


class TestHeaders:
    """Test HTTP headers configuration."""

    def test_headers_defined(self):
        """Test that headers are properly defined."""
        assert 'User-Agent' in zixun.HEADERS
        assert 'Content-Type' in zixun.HEADERS
        assert 'Authorization' in zixun.HEADERS
        assert 'token' in zixun.HEADERS
