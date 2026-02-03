"""Tests for main.py - Orchestrator."""
import os
import sys
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestMainConfig:
    """Test main orchestrator configuration."""

    def test_scripts_list_defined(self):
        """Verify scripts list is defined."""
        assert hasattr(main, 'SCRIPTS')
        assert len(main.SCRIPTS) == 4
        assert 'arkm.py' in main.SCRIPTS
        assert 'bianjk.py' in main.SCRIPTS
        assert 'zixun.py' in main.SCRIPTS
        assert 'botsever.py' in main.SCRIPTS


class TestScriptList:
    """Test script list contents."""

    def test_all_required_scripts_present(self):
        """Verify all required monitoring scripts are listed."""
        expected_scripts = [
            'arkm.py',
            'bianjk.py',
            'zixun.py',
            'botsever.py'
        ]

        for script in expected_scripts:
            assert script in main.SCRIPTS

    def test_script_order(self):
        """Verify scripts are in expected order."""
        assert main.SCRIPTS[0] == 'arkm.py'
        assert main.SCRIPTS[1] == 'bianjk.py'
        assert main.SCRIPTS[2] == 'zixun.py'
        assert main.SCRIPTS[3] == 'botsever.py'


class TestStartScript:
    """Test script startup functionality."""

    @patch('main.subprocess.Popen')
    def test_start_script_success(self, mock_popen):
        """Test successful script startup."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = main.start_script('arkm.py')

        assert result is True
        mock_popen.assert_called_once()

    @patch('main.subprocess.Popen')
    def test_start_script_error(self, mock_popen):
        """Test script startup error handling."""
        mock_popen.side_effect = Exception('Startup failed')

        result = main.start_script('arkm.py')

        assert result is False


class TestProcessTracking:
    """Test process tracking functionality."""

    def test_running_processes_starts_empty(self):
        """Test that running_processes starts empty."""
        # Reset and check
        main.running_processes = {}
        assert main.running_processes == {}

    @patch('main.subprocess.Popen')
    def test_running_processes_populated_on_start(self, mock_popen):
        """Test that running_processes is populated when scripts start."""
        main.running_processes = {}

        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        main.start_script('arkm.py')

        assert 'arkm.py' in main.running_processes
        assert main.running_processes['arkm.py']['type'] == 'process'
