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

import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


# Set up paths so we can import rh modules.
THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR))

# pylint: disable=wrong-import-position
import rh.results  # noqa: E402
import rh.utils  # noqa: E402


# pylint: enable=wrong-import-position


# Load pre-upload.py as a module (since its filename has a hyphen).
spec = importlib.util.spec_from_file_location(
    "pre_upload", os.path.join(THIS_DIR, "pre-upload.py")
)
pre_upload = importlib.util.module_from_spec(spec)
sys.modules["pre_upload"] = pre_upload
spec.loader.exec_module(pre_upload)


# pylint: disable=protected-access
class PreUploadMainTests(unittest.TestCase):
    """Test pre-upload.py main/direct_main parameter propagation."""

    @mock.patch("pre_upload._run_projects_hooks", return_value=True)
    def test_main_fix_propagation(self, mock_run):
        """Verify main(..., fix=True, yes=True) passes flags to _run_projects_hooks."""
        pre_upload.main(["project"], fix=True, yes=True)
        mock_run.assert_called_once_with(
            ["project"], [None], fix=True, yes=True
        )

    @mock.patch("pre_upload._run_project_hooks", return_value=True)
    @mock.patch("pre_upload._attempt_fixes")
    def test_run_projects_hooks_fix_propagation(self, mock_attempt, mock_run):
        """Verify _run_projects_hooks passes fix=True to _attempt_fixes."""
        pre_upload._run_projects_hooks(["p1"], [None], fix=True, yes=True)
        mock_run.assert_called_once_with(
            "p1",
            proj_dir=None,
            jobs=None,
            from_git=False,
            commit_list=None,
        )
        mock_attempt.assert_called_once_with([True], fix=True, yes=True)

    @mock.patch("pre_upload._run_projects_hooks", return_value=True)
    @mock.patch("pre_upload._identify_project", return_value="project")
    @mock.patch("rh.git.is_git_repository", return_value=True)
    @mock.patch("rh.utils.run")
    def test_direct_main_fix_yes(
        self, mock_run_cmd, _mock_is_git, _mock_identify, mock_run
    ):
        """Verify direct_main with --fix and --yes passes flags to _run_projects_hooks."""
        mock_run_cmd.return_value = rh.utils.CompletedProcess(
            stdout="/path/to/repo/.git\n"
        )
        pre_upload.direct_main(["--fix", "--yes", "commit_hash"])
        mock_run.assert_called_once_with(
            ["project"],
            ["/path/to/repo"],
            jobs=None,
            from_git=False,
            commit_list=["commit_hash"],
            fix=True,
            yes=True,
        )

    @mock.patch("sys.stdin.isatty", return_value=True)
    @mock.patch("rh.terminal.boolean_prompt")
    @mock.patch("rh.utils.run")
    def test_attempt_fixes_with_fix_flag(
        self, mock_run, mock_prompt, _mock_isatty
    ):
        """Verify _attempt_fixes with fix=True executes fixups without prompting."""
        hook_result = rh.results.HookResult(
            "test_hook",
            "test_project",
            "test_commit",
            error="error",
            fixup_cmd=["fix_cmd"],
        )
        proj_result = rh.results.ProjectResults(
            "test_project", "/workdir", [hook_result]
        )

        pre_upload._attempt_fixes([proj_result], fix=True)

        mock_prompt.assert_not_called()
        mock_run.assert_called_once()

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("sys.stdin.isatty", return_value=False)
    @mock.patch("rh.utils.run")
    def test_attempt_fixes_non_interactive_no_fix(
        self, mock_run, _mock_isatty, mock_stderr
    ):
        """Verify _attempt_fixes without fix in non-interactive mode does not run fixups."""
        hook_result = rh.results.HookResult(
            "test_hook",
            "test_project",
            "test_commit",
            error="error",
            fixup_cmd=["fix_cmd"],
        )
        proj_result = rh.results.ProjectResults(
            "test_project", "/workdir", [hook_result]
        )

        pre_upload._attempt_fixes([proj_result], fix=False, yes=True)

        mock_run.assert_not_called()
        self.assertIn("repo upload --fix", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
