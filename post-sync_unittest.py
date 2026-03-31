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

"""Unittests for the post-sync module."""

import configparser
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
# We have to import our local modules after the sys.path tweak.
sys.path.insert(0, str(THIS_DIR))


# Import the post-sync script as a module.
spec = importlib.util.spec_from_file_location(
    "post_sync", THIS_DIR / "post-sync.py"
)
post_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_sync)


class PostSyncTests(unittest.TestCase):
    """Verify behavior of post-sync dispatcher."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tempdir)
        self.manifest_dir = self.repo_root / ".repo" / "manifests"
        self.manifest_dir.mkdir(parents=True)
        self.config_file = self.manifest_dir / "GLOBAL-POSTSYNC.cfg"

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @mock.patch("rh.git.find_repo_root")
    def test_no_repo_root(self, mock_find_root):
        """Check behavior when no repo root is found."""
        mock_find_root.return_value = None
        self.assertEqual(0, post_sync.main())

    @mock.patch("rh.git.find_repo_root")
    def test_no_config_file(self, mock_find_root):
        """Check behavior when no config file exists."""
        mock_find_root.return_value = str(self.repo_root)
        self.assertEqual(0, post_sync.main())

    @mock.patch("rh.git.find_repo_root")
    @mock.patch("rh.utils.run")
    def test_hook_execution(self, mock_run, mock_find_root):
        """Check successful hook execution."""
        mock_find_root.return_value = str(self.repo_root)

        # Create a dummy hook script.
        hook_relative_path = "hooks/test-hook.py"
        hook_path = self.repo_root / hook_relative_path
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("#!/usr/bin/env python3\npass\n")
        hook_path.chmod(0o755)

        # Create the config file with placeholders.
        config = configparser.RawConfigParser()
        config.add_section("Hook Scripts")
        config.set(
            "Hook Scripts",
            "test",
            str(hook_relative_path) + " --root=${REPO_ROOT} "
            "--duration=${REPO_SYNC_DURATION}",
        )
        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

        mock_run.return_value = mock.Mock(returncode=0)

        self.assertEqual(0, post_sync.main(sync_duration_seconds=100))

        # Verify rh.utils.run call.
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertEqual(str(hook_path), cmd[0])
        self.assertIn(f"--root={self.repo_root}", cmd)
        self.assertIn("--duration=100", cmd)
        self.assertEqual(self.repo_root, kwargs["cwd"])
        self.assertEqual(str(self.repo_root), kwargs["extra_env"]["REPO_ROOT"])
        self.assertEqual(
            "100", kwargs["extra_env"]["REPO_HOOK_SYNC_DURATION_SECONDS"]
        )

    @mock.patch("rh.git.find_repo_root")
    @mock.patch("rh.utils.run")
    def test_hook_failure(self, mock_run, mock_find_root):
        """Check behavior when a hook fails."""
        mock_find_root.return_value = str(self.repo_root)

        # Create a dummy hook script.
        hook_relative_path = "hooks/fail-hook.sh"
        hook_path = self.repo_root / hook_relative_path
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("#!/bin/sh\nexit 1\n")
        hook_path.chmod(0o755)

        # Create the config file.
        config = configparser.RawConfigParser()
        config.add_section("Hook Scripts")
        config.set("Hook Scripts", "fail", hook_relative_path)
        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

        mock_run.return_value = mock.Mock(returncode=1)

        self.assertEqual(1, post_sync.main())


if __name__ == "__main__":
    unittest.main()
