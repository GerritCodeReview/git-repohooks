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

"""Repo post-sync hook dispatcher.

This script acts as an entry point for repo post-sync hooks. It reads a
configuration file from the manifest repository to discover and execute
registered post-sync hooks.
"""

import argparse
import configparser
import os
from pathlib import Path
import shlex
import sys
from typing import Optional, Union


# Assert some minimum Python versions as we don't test or support any others.
if sys.version_info < (3, 6):
    print("repohooks: error: Python-3.6+ is required", file=sys.stderr)
    sys.exit(1)


THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR.parent))


# We have to import our local modules after the sys.path tweak.  We can't use
# relative imports because this is an executable program, not a module.
# pylint: disable=wrong-import-position
import rh.git
import rh.hooks
import rh.utils


class PostSyncPlaceholders(rh.hooks.Placeholders):
    """Placeholders for post-sync hooks."""

    def __init__(self, repo_root: Path, sync_duration: Optional[int] = None):
        """Initialize.

        Args:
            repo_root: The top level of the repo checkout.
            sync_duration: The total time taken by the sync operation.
        """
        super().__init__()
        self._repo_root = repo_root
        self._sync_duration = sync_duration

    @property
    def var_REPO_ROOT(self) -> str:
        """The absolute path of the root of the repo checkout."""
        return str(self._repo_root)

    @property
    def var_REPO_SYNC_DURATION(self) -> str:
        """The total time taken by the sync operation."""
        return (
            str(self._sync_duration) if self._sync_duration is not None else ""
        )


def main(
    repo_root: Optional[Union[str, Path]] = None,
    sync_duration_seconds: Optional[int] = None,
) -> int:
    """Main function invoked directly by repo post-sync."""
    if not repo_root:
        repo_root = os.environ.get("REPO_ROOT")
    if not repo_root:
        repo_root = rh.git.find_repo_root()

    if not repo_root:
        return 0

    if sync_duration_seconds is None:
        val = os.environ.get("REPO_HOOK_SYNC_DURATION_SECONDS")
        if val:
            try:
                sync_duration_seconds = int(val)
            except ValueError:
                pass

    repo_root_path = Path(repo_root)

    # Look for a registration file in the manifest repository.
    config_file = repo_root_path / ".repo" / "manifests" / "GLOBAL-POSTSYNC.cfg"
    if not config_file.exists():
        return 0

    # Prepare environment for the subprocess calls.
    extra_env = {
        "REPO_ROOT": str(repo_root_path),
    }
    if sync_duration_seconds is not None:
        extra_env["REPO_HOOK_SYNC_DURATION_SECONDS"] = str(
            sync_duration_seconds
        )

    exit_code = 0
    config = configparser.RawConfigParser()
    config.read(config_file, encoding="utf-8")

    if not config.has_section("Hook Scripts"):
        return 0

    placeholders = PostSyncPlaceholders(
        repo_root_path, sync_duration_seconds
    )

    for name, command in config.items("Hook Scripts"):
        cmd = shlex.split(command)
        if not cmd:
            continue

        # Expand placeholders in the command arguments.
        cmd = placeholders.expand_vars(cmd)

        # Resolve the hook path relative to the repo root if it is not absolute.
        hook_path = Path(cmd[0])
        if not hook_path.is_absolute():
            hook_path = repo_root_path / hook_path

        if not hook_path.exists():
            print(
                f"Warning: Registered post-sync hook '{name}' not found: "
                f"{hook_path}",
                file=sys.stderr,
            )
            continue

        # Replace the first element with the resolved path.
        cmd[0] = str(hook_path)

        # Execute the hook as a subprocess.
        result = rh.utils.run(
            cmd, cwd=repo_root_path, extra_env=extra_env, check=False
        )
        if result.returncode:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", help="The top level of the repo checkout."
    )
    parser.add_argument(
        "--sync-duration-seconds",
        type=int,
        help="The total time taken by the sync operation.",
    )
    opts = parser.parse_args()
    sys.exit(
        main(
            repo_root=opts.repo_root,
            sync_duration_seconds=opts.sync_duration_seconds,
        )
    )
