#!/usr/bin/env python3
#
# Copyright 2026 Google Inc. All Rights Reserved.

import unittest
from unittest.mock import patch
import sys
from io import StringIO
import importlib.util
import os
import pathlib

# Load post-sync.py dynamically since it's a script without a .py extension in standard imports
hook_path = os.path.join(os.path.dirname(__file__), 'repomon_promotion.py')
spec = importlib.util.spec_from_file_location("post_sync", hook_path)
post_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_sync)

class TestPostSyncHook(unittest.TestCase):
    @patch('os.path.isdir', return_value=True)
    @patch.object(post_sync, 'is_established_workspace', return_value=True)
    @patch('os.path.exists', return_value=False)
    @patch('sys.stdout', new_callable=StringIO)
    def test_fast_sync(self, mock_stdout, mock_exists, mock_is_established, mock_isdir):
        # Duration below threshold (e.g., 100s)
        self.assertEqual(post_sync.main(sync_duration_seconds=100), 0)
        self.assertEqual(mock_stdout.getvalue(), "")

    @patch('os.path.isdir', return_value=True)
    @patch.object(post_sync, 'is_established_workspace', return_value=True)
    @patch('os.path.exists', return_value=False)
    @patch('sys.stdout', new_callable=StringIO)
    def test_slow_sync(self, mock_stdout, mock_exists, mock_is_established, mock_isdir):
        # Duration above threshold (e.g., 1000s)
        self.assertEqual(post_sync.main(sync_duration_seconds=1000), 0)
        output = mock_stdout.getvalue()
        self.assertIn("Notice: Your syncs are taking too long", output)
        self.assertIn("install Repomon", output)

    @patch('os.path.isdir', return_value=True)
    @patch.object(post_sync, 'is_established_workspace', return_value=True)
    @patch('os.path.exists', return_value=False)
    @patch('sys.stdout', new_callable=StringIO)
    def test_no_duration(self, mock_stdout, mock_exists, mock_is_established, mock_isdir):
        # No duration passed
        self.assertEqual(post_sync.main(), 0)
        self.assertEqual(mock_stdout.getvalue(), "")

    @patch('os.path.isdir', return_value=True)
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_already_installed(self, mock_stdout, mock_exists, mock_isdir):
        # Duration above threshold, but already installed
        self.assertEqual(post_sync.main(sync_duration_seconds=1000), 0)
        self.assertEqual(mock_stdout.getvalue(), "")

    @patch('subprocess.check_output')
    @patch('os.path.exists')
    @patch('os.path.getmtime')
    @patch('time.time')
    def test_is_established_workspace(self, mock_time, mock_getmtime, mock_exists, mock_check_output):
        # Make stat call fail to test fallback
        mock_check_output.side_effect = Exception("stat failed")

        mock_exists.return_value = True
        mock_getmtime.return_value = 1000
        mock_time.return_value = 2000

        # Threshold is 24 hours (86400 seconds)
        # Current time (2000) - mtime (1000) = 1000 < 86400 -> False
        self.assertFalse(post_sync.is_established_workspace('/fake/root'))

        mock_time.return_value = 100000
        # Current time (100000) - mtime (1000) = 99000 > 86400 -> True
        self.assertTrue(post_sync.is_established_workspace('/fake/root'))

        mock_exists.return_value = False
        self.assertFalse(post_sync.is_established_workspace('/fake/root'))


    @patch('subprocess.check_output')
    @patch('time.time')
    def test_is_established_workspace_stat_success(self, mock_time, mock_check_output):
        mock_check_output.return_value = "1000"
        mock_time.return_value = 2000

        # Threshold is 24 hours (86400 seconds)
        # Current time (2000) - birth (1000) = 1000 < 86400 -> False
        self.assertFalse(post_sync.is_established_workspace('/fake/root'))

        mock_time.return_value = 100000
        # Current time (100000) - birth (1000) = 99000 > 86400 -> True
        self.assertTrue(post_sync.is_established_workspace('/fake/root'))


if __name__ == '__main__':
    unittest.main()
