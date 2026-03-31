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
import rh.utils


def main(
    repo_root: Optional[Union[str, Path]] = None,
) -> int:
    """Main function invoked directly by repo post-sync."""
    if not repo_root:
        repo_root = os.environ.get("REPO_ROOT")
    if not repo_root:
        repo_root = rh.git.find_repo_root()

    if not repo_root:
        return 0

    repo_root = Path(repo_root)

    # Look for a registration file in the manifest repository.
    config_file = repo_root / ".repo" / "manifests" / "GLOBAL-POSTSYNC.cfg"
    if not config_file.exists():
        return 0

    # Prepare environment for the subprocess calls.
    extra_env = {
        "REPO_ROOT": str(repo_root),
    }

    exit_code = 0
    config = configparser.RawConfigParser()
    config.read(config_file, encoding="utf-8")

    if not config.has_section("Hook Scripts"):
        return 0

    for name, command in config.items("Hook Scripts"):
        cmd = shlex.split(command)
        if not cmd:
            continue

        # Resolve the hook path relative to the repo root if it is not absolute.
        hook_path = Path(cmd[0])
        if not hook_path.is_absolute():
            hook_path = repo_root / hook_path

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
            cmd, cwd=repo_root, extra_env=extra_env, check=False
        )
        if result.returncode:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
