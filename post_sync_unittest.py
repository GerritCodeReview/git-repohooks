#!/usr/bin/env python3
# Copyright 2026 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the \"License\");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an \"AS IS\" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unittests for the post_sync module."""

from pathlib import Path
import sys
import unittest
from unittest import mock


THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR))

# We have to import our local modules after the sys.path tweak.
# pylint: disable=wrong-import-position
import post_sync


class PostSyncTests(unittest.TestCase):
    """Verify behavior of post_sync dispatcher."""

    def setUp(self):
        self.topdir = Path("/mock/top")
        self.config_file = self.topdir / ".repo" / "manifests" / "POSTSYNC.cfg"

    @mock.patch("rh.git.find_repo_root")
    def test_no_repo_root(self, mock_find_root):
        """Check behavior when no repo root is found."""
        mock_find_root.return_value = None
        self.assertEqual(0, post_sync.main())

    @mock.patch("rh.git.find_repo_root")
    @mock.patch("os.path.exists")
    def test_no_config_file(self, mock_exists, mock_find_root):
        """Check behavior when no config file exists."""
        mock_find_root.return_value = str(self.topdir)
        mock_exists.return_value = False
        self.assertEqual(0, post_sync.main())

    @mock.patch("rh.git.find_repo_root")
    @mock.patch("os.path.exists")
    @mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data="hooks/test-hook.py\n",
    )
    @mock.patch("rh.utils.run")
    def test_hook_execution(
        self, mock_run, _mock_open, mock_exists, mock_find_root
    ):
        """Check successful hook execution."""
        mock_find_root.return_value = str(self.topdir)
        # We need to mock exists for both config_file and hook_path
        mock_exists.side_effect = lambda p: str(p) in (
            str(self.config_file),
            str(self.topdir / "hooks/test-hook.py"),
        )

        mock_run.return_value = mock.Mock(returncode=0)

        self.assertEqual(0, post_sync.main(sync_duration_seconds=100))

        # Verify rh.utils.run call
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn(sys.executable, cmd)
        self.assertIn(str(self.topdir / "hooks/test-hook.py"), cmd)
        self.assertIn("--repo-topdir=" + str(self.topdir), cmd)
        self.assertIn("--sync-duration-seconds=100", cmd)
        self.assertEqual(str(self.topdir), kwargs["cwd"])
        self.assertEqual(str(self.topdir), kwargs["extra_env"]["REPO_TOPDIR"])

    @mock.patch("rh.git.find_repo_root")
    @mock.patch("os.path.exists")
    @mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data="hooks/fail-hook.py\n",
    )
    @mock.patch("rh.utils.run")
    def test_hook_failure(
        self, mock_run, _mock_open, mock_exists, mock_find_root
    ):
        """Check behavior when a hook fails."""
        mock_find_root.return_value = str(self.topdir)
        mock_exists.return_value = True
        mock_run.return_value = mock.Mock(returncode=1)

        self.assertEqual(1, post_sync.main())


if __name__ == "__main__":
    unittest.main()
