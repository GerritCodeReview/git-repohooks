#!/usr/bin/env python3
# Copyright 2026 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unittests for pre-upload.py."""

import importlib
from pathlib import Path
import sys
import unittest
from unittest import mock

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR))

# Import pre-upload.py using importlib because of the hyphen in the name.
pre_upload = importlib.import_module('pre-upload')
import rh
import rh.results


class AttemptFixesTests(unittest.TestCase):
    """Verify _attempt_fixes behavior."""

    def setUp(self):
        self.project_name = "project-name"
        self.proj_dir = "/.../repo/dir"
        self.workdir = self.proj_dir

    @mock.patch('sys.exit')
    @mock.patch('rh.utils.run')
    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.terminal.str_prompt')
    def test_no_fixups(self, mock_str_prompt, mock_bool_prompt, mock_run, mock_exit):
        """Test when no fixups are available."""
        results = [rh.results.ProjectResults(self.project_name, self.workdir, [])]
        pre_upload._attempt_fixes(results)
        self.assertFalse(mock_run.called)
        self.assertFalse(mock_exit.called)

    @mock.patch('sys.exit')
    @mock.patch('rh.utils.run')
    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.terminal.str_prompt')
    def test_fixups_applied_no_errors(self, mock_str_prompt, mock_bool_prompt, mock_run, mock_exit):
        """Test when fixups are applied and there are no errors."""
        mock_bool_prompt.return_value = True
        mock_run.return_value = rh.utils.CompletedProcess(returncode=0)

        # Create a HookResult with a fixup
        result = rh.results.HookResult(
            "hook", self.project_name, "commit", "error",
            fixup_cmd=["fixup_cmd"], files=["file.txt"], warning=True
        )
        project_results = rh.results.ProjectResults(self.project_name, self.workdir, [result])

        # We expect sys.exit(1) to be called because fixes are applied and there are no errors.
        pre_upload._attempt_fixes([project_results])

        self.assertTrue(mock_run.called)
        mock_exit.assert_called_once_with(1)

    @mock.patch('sys.exit')
    @mock.patch('rh.utils.run')
    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.terminal.str_prompt')
    def test_fixups_applied_with_errors(self, mock_str_prompt, mock_bool_prompt, mock_run, mock_exit):
        """Test when fixups are applied but there are blocking errors."""
        mock_bool_prompt.return_value = True
        mock_run.return_value = rh.utils.CompletedProcess(returncode=0)

        # Create a HookResult with a fixup (warning)
        result1 = rh.results.HookResult(
            "hook1", self.project_name, "commit", "warning",
            fixup_cmd=["fixup_cmd"], files=["file.txt"], warning=True
        )
        # Create a HookResult with an error
        result2 = rh.results.HookResult(
            "hook2", self.project_name, "commit", "error", warning=False
        )

        project_results = rh.results.ProjectResults(self.project_name, self.workdir, [result1, result2])

        # We expect sys.exit not to be called because there are blocking errors.
        pre_upload._attempt_fixes([project_results])

        self.assertTrue(mock_run.called)
        self.assertFalse(mock_exit.called)

    @mock.patch('sys.exit')
    @mock.patch('rh.utils.run')
    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.terminal.str_prompt')
    def test_fixups_rejected(self, mock_str_prompt, mock_bool_prompt, mock_run, mock_exit):
        """Test when fixups are available but rejected by user."""
        mock_bool_prompt.return_value = False

        result = rh.results.HookResult(
            "hook", self.project_name, "commit", "error",
            fixup_cmd=["fixup_cmd"], files=["file.txt"], warning=True
        )
        project_results = rh.results.ProjectResults(self.project_name, self.workdir, [result])

        pre_upload._attempt_fixes([project_results])

        self.assertFalse(mock_run.called)
        self.assertFalse(mock_exit.called)


if __name__ == '__main__':
    unittest.main()
