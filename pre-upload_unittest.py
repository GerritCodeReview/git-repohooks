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
import os
import sys
import unittest
from unittest import mock


# Set up paths so we can import rh modules
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(THIS_DIR))

import rh.utils


# Load pre-upload.py as a module (since its filename has a hyphen)
spec = importlib.util.spec_from_file_location(
    "pre_upload", os.path.join(THIS_DIR, "pre-upload.py")
)
pre_upload = importlib.util.module_from_spec(spec)
sys.modules["pre_upload"] = pre_upload
spec.loader.exec_module(pre_upload)


class PreUploadMainTests(unittest.TestCase):
    """Test pre-upload.py main/direct_main parameter propagation."""

    @mock.patch("pre_upload._run_projects_hooks", return_value=True)
    def test_main_yes_propagation(self, mock_run):
        """Verify main(..., yes=True) passes yes=True to _run_projects_hooks."""
        pre_upload.main(["project"], yes=True)
        mock_run.assert_called_once_with(["project"], [None], yes=True)

    @mock.patch("pre_upload._run_project_hooks", return_value=True)
    @mock.patch("pre_upload._attempt_fixes")
    def test_run_projects_hooks_yes_propagation(self, mock_attempt, mock_run):
        """Verify _run_projects_hooks passes yes=True down."""
        pre_upload._run_projects_hooks(["p1"], [None], yes=True)
        mock_run.assert_called_once_with(
            "p1",
            proj_dir=None,
            jobs=None,
            from_git=False,
            commit_list=None,
            yes=True,
        )
        mock_attempt.assert_called_once_with([True], yes=True)

    @mock.patch("pre_upload._run_project_hooks_in_cwd", return_value=True)
    @mock.patch("os.chdir")
    def test_run_project_hooks_yes_propagation(self, mock_chdir, mock_run_cwd):
        """Verify _run_project_hooks passes yes=True to _run_project_hooks_in_cwd."""
        with mock.patch("rh.utils.run") as mock_run_cmd:
            mock_run_cmd.return_value = rh.utils.CompletedProcess(
                stdout="dir1\n"
            )
            pre_upload._run_project_hooks("p1", yes=True)
            mock_run_cwd.assert_called_once_with(
                "p1",
                "dir1",
                mock.ANY,
                jobs=None,
                from_git=False,
                commit_list=None,
                yes=True,
            )

    @mock.patch("pre_upload._get_project_config")
    def test_run_project_hooks_in_cwd_yes_propagation(self, mock_config):
        """Verify _run_project_hooks_in_cwd calls callable_builtin_hooks(yes=True)."""
        mock_cfg = mock.MagicMock()
        mock_cfg.callable_builtin_hooks.return_value = []
        mock_cfg.callable_custom_hooks.return_value = []
        mock_config.return_value = mock_cfg

        output = pre_upload.Output("p1")
        pre_upload._run_project_hooks_in_cwd("p1", "dir1", output, yes=True)
        mock_cfg.callable_builtin_hooks.assert_called_once_with(yes=True)

    @mock.patch("pre_upload._run_projects_hooks", return_value=True)
    @mock.patch("pre_upload._identify_project", return_value="project")
    @mock.patch("rh.git.is_git_repository", return_value=True)
    @mock.patch("rh.utils.run")
    def test_direct_main_yes(
        self, mock_run_cmd, mock_is_git, mock_identify, mock_run
    ):
        """Verify direct_main with --yes passes yes=True to _run_projects_hooks."""
        mock_run_cmd.return_value = rh.utils.CompletedProcess(
            stdout="/path/to/repo/.git\n"
        )
        pre_upload.direct_main(["--yes", "commit_hash"])
        mock_run.assert_called_once_with(
            ["project"],
            ["/path/to/repo"],
            jobs=None,
            from_git=False,
            commit_list=["commit_hash"],
            yes=True,
        )


if __name__ == "__main__":
    unittest.main()
