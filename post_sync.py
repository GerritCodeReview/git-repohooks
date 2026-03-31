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

import os
from pathlib import Path
import sys


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


def main(repo_topdir=None, **kwargs):
    """Main function invoked directly by repo post-sync.

    Args:
        repo_topdir: The top level of the repo checkout.
        kwargs: Additional arguments passed by repo.

    Returns:
        The exit code of the hooks (0 if all passed).
    """
    if not repo_topdir:
        repo_topdir = rh.git.find_repo_root()

    if not repo_topdir:
        return 0

    # Look for a registration file in the manifest repository
    config_file = os.path.join(repo_topdir, ".repo", "manifests", "POSTSYNC.cfg")
    if not os.path.exists(config_file):
        return 0

    # Prepare environment for the subprocess calls
    extra_env = {"REPO_TOPDIR": repo_topdir}
    for key, value in kwargs.items():
        extra_env[f"REPO_HOOK_{key.upper()}"] = str(value)

    exit_code = 0
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            hook_path = os.path.join(repo_topdir, line)
            if not os.path.exists(hook_path):
                print(
                    f"Warning: Registered post-sync hook not found: {hook_path}",
                    file=sys.stderr,
                )
                continue

            try:
                # Determine how to execute the hook
                cmd = [hook_path]
                if hook_path.endswith(".py"):
                    cmd = [sys.executable, hook_path]

                # Pass context as command-line arguments
                cmd.append(f"--repo-topdir={repo_topdir}")
                for key, value in kwargs.items():
                    # Convert sync_duration_seconds -> --sync-duration-seconds
                    arg_name = key.replace("_", "-")
                    cmd.append(f"--{arg_name}={value}")

                # Execute the hook as a subprocess
                result = rh.utils.run(
                    cmd, cwd=repo_topdir, extra_env=extra_env, check=False
                )
                if result.returncode:
                    exit_code = result.returncode
            except Exception as e:
                print(
                    f"Warning: Failed to execute post-sync hook '{line}': {e}",
                    file=sys.stderr,
                )
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sync_duration_seconds=1000))
