"""Pytest configuration and fixtures."""
import os
import sys

# Set up environment variables for testing before importing modules
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_bot_token'
os.environ['TELEGRAM_CHAT_ID'] = 'test_chat_id'
os.environ['ARKHAM_API_KEY'] = 'test_arkham_key'
os.environ['MLION_API_KEY'] = 'test_mlion_key'
os.environ['ARKHAM_TOPIC_ID'] = '1'
os.environ['BINANCE_TOPIC_ID'] = '3'
os.environ['ZIXUN_TOPIC_ID'] = '4'
os.environ['BOTSEVER_TOPIC_ID'] = '13'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def reset_modules():
    """Reset module state between tests."""
    yield
    # Modules will be reimported fresh for each test that needs them
