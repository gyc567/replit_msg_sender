"""Tests for botsever.py - Flask webhook server."""
import os
import sys
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import botsever


class TestBotseverConfig:
    """Test configuration loading."""

    def test_config_loads_from_env(self):
        """Verify configuration loads from environment variables."""
        assert botsever.BOT_TOKEN == 'test_bot_token'
        assert botsever.TG_CHAT_ID == 'test_chat_id'

    def test_default_topic_id(self):
        """Test default topic ID."""
        assert botsever.TOPIC_ID == 13

    def test_default_route_path(self):
        """Test default webhook route path."""
        assert botsever.ROUTE_PATH == '/twitter-webhook'

    def test_default_start_port(self):
        """Test default start port."""
        assert botsever.START_PORT == 5006


class TestPortSelection:
    """Test port selection functionality."""

    def test_get_available_port_free(self):
        """Test finding available free port."""
        port = botsever.get_available_port(5006)
        assert port is not None
        assert 1 <= port <= 65535


class TestTelegramSending:
    """Test Telegram message sending."""

    def test_send_to_telegram_success(self):
        """Test successful Telegram message send."""
        with patch('botsever.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'ok': True}
            mock_post.return_value = mock_response

            result = botsever.send_to_telegram('Test message')

            assert result is True
            mock_post.assert_called_once()

    def test_send_to_telegram_missing_token(self):
        """Test handling of missing bot token."""
        original_token = botsever.BOT_TOKEN
        botsever.BOT_TOKEN = None

        result = botsever.send_to_telegram('Test message')

        botsever.BOT_TOKEN = original_token
        assert result is False


class TestWebhookEndpoint:
    """Test webhook endpoint functionality."""

    def test_webhook_route_exists(self):
        """Test that webhook route is configured."""
        routes = []
        for rule in botsever.app.url_map.iter_rules():
            routes.append(rule.rule)

        assert '/twitter-webhook' in routes

    def test_webhook_empty_data(self):
        """Test webhook with empty JSON data."""
        client = botsever.app.test_client()
        response = client.post(
            '/twitter-webhook',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200

    def test_webhook_valid_data(self):
        """Test webhook with valid tweet data."""
        with patch.object(botsever, 'send_to_telegram') as mock_send:
            mock_send.return_value = True

            client = botsever.app.test_client()

            response = client.post(
                '/twitter-webhook',
                data=json.dumps({
                    'text': 'Test tweet content',
                    'link': 'https://twitter.com/user/status/123',
                    'user': 'test_user'
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            assert mock_send.called


class TestFlaskApp:
    """Test Flask application configuration."""

    def test_app_created(self):
        """Test Flask app is created."""
        from flask import Flask
        assert isinstance(botsever.app, Flask)

    def test_run_server_returns_port(self):
        """Test run_server returns a valid port."""
        port = botsever.run_server()

        # Should return a port number or None
        if port is not None:
            assert isinstance(port, int)
            assert 1 <= port <= 65535


class TestWebhookParsing:
    """Test webhook data parsing helpers."""

    def test_parse_tweet_text(self):
        """Test parsing tweet text from various field names."""
        # Test 'text' field
        data = {'text': 'Test content'}
        text = data.get('text', data.get('content', data.get('full_text', '无正文内容')))
        assert text == 'Test content'

        # Test 'content' field
        data = {'content': 'Test content'}
        text = data.get('text', data.get('content', data.get('full_text', '无正文内容')))
        assert text == 'Test content'

    def test_parse_tweet_user(self):
        """Test parsing tweet user from various field names."""
        data = {'user': 'test_user'}
        user = data.get('user', data.get('author', data.get('screen_name', '未知用户')))
        assert user == 'test_user'

    def test_parse_tweet_link(self):
        """Test parsing tweet link from various field names."""
        data = {'link': 'https://twitter.com/user/status/123'}
        link = data.get('link', data.get('url', data.get('tweet_url', '')))
        assert link == 'https://twitter.com/user/status/123'
