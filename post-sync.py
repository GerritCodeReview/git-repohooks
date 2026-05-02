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
from pathlib import Path
import sys
from typing import List, Optional


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
import rh.config  # isort: skip
import rh.git  # isort: skip
import rh.hooks  # isort: skip
import rh.terminal  # isort: skip
import rh.utils  # isort: skip


class PostSyncPlaceholders(rh.hooks.Placeholders):
    """Placeholders for post-sync hooks."""

    def __init__(self, repo_root: Path, sync_duration: Optional[int] = None, sync_type: Optional[str] = None):
        """Initialize.

        Args:
            repo_root: The top level of the repo checkout.
            sync_duration: The total time taken by the sync operation.
            sync_type: The type of sync operation executed.
        """
        super().__init__()
        self._repo_root = repo_root
        self._sync_duration = sync_duration
        self._sync_type = sync_type

    @property
    def var_REPO_ROOT(self) -> str:
        """The absolute path of the root of the repo checkout."""
        return str(self._repo_root)

    @property
    def var_REPO_OUTER_ROOT(self) -> str:
        """The absolute path of the outermost root of the repo checkout."""
        return str(self._repo_root)

    @property
    def var_REPO_SYNC_DURATION(self) -> str:
        """The total time taken by the sync operation."""
        return str(self._sync_duration) if self._sync_duration is not None else ""

    @property
    def var_REPO_SYNC_TYPE(self) -> str:
        """The type of sync operation executed."""
        return str(self._sync_type) if self._sync_type is not None else ""


def _run_post_sync_hooks(
    repo_root_path: Path, sync_duration_seconds: Optional[int], sync_type: Optional[str]
) -> int:
    """Run the registered post-sync hooks."""

    config_file = repo_root_path / ".repo" / "manifests" / "GLOBAL-POSTSYNC.cfg"
    if not config_file.exists():
        return 0

    try:
        settings = rh.config.PostSyncSettings(str(config_file))
    except rh.config.ValidationError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 1

    if not settings.custom_hooks:
        return 0

    # Prepare environment for the subprocess calls (Explicitly omitting sync variables)
    extra_env = {
        "REPO_ROOT": str(repo_root_path),
    }

    exit_code = 0
    placeholders = PostSyncPlaceholders(repo_root_path, sync_duration_seconds, sync_type)
    color = rh.terminal.Color()

    for name in settings.custom_hooks:
        cmd = settings.custom_hook(name)
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
                f"error: Registered post-sync hook '{name}' not found: "
                f"{hook_path}",
                file=sys.stderr,
            )
            return 1

        # Replace the first element with the resolved path.
        cmd[0] = str(hook_path.resolve())

        # Print running status.
        status_line = f"[{color.color(color.YELLOW, 'RUNNING')}] {name}"
        rh.terminal.print_status_line(status_line)

        # Execute the hook as a subprocess.
        result = rh.utils.run(
            cmd, cwd=repo_root_path, extra_env=extra_env, check=False
        )

        if result.returncode:
            exit_code = result.returncode
            status_line = f"[{color.color(color.RED, 'FAILED')}] {name}"
            rh.terminal.print_status_line(status_line, print_newline=True)
        else:
            status_line = f"[{color.color(color.GREEN, 'PASSED')}] {name}"
            rh.terminal.print_status_line(status_line, print_newline=True)

    return exit_code


def main(repo_topdir=None, **kwargs) -> int:
    """Main function invoked directly by repo."""
    if not repo_topdir:
        try:
            repo_root = rh.git.find_repo_root()
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    else:
        repo_root = repo_topdir

    sync_duration_seconds = kwargs.get("sync_duration_seconds")
    sync_type = kwargs.get("sync_type")

    return _run_post_sync_hooks(Path(repo_root), sync_duration_seconds, sync_type)


def direct_main(argv: List[str]) -> int:
    """Run hooks directly (outside of the context of repo)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", help="The top level of the repo checkout."
    )
    parser.add_argument(
        "--sync-duration-seconds",
        type=int,
        help="The total time taken by the sync operation.",
    )
    parser.add_argument(
        "--sync-type",
        help="The type of sync operation executed.",
    )

    opts = parser.parse_args(argv)
    return main(
        repo_topdir=opts.repo_root,
        sync_duration_seconds=opts.sync_duration_seconds,
        sync_type=opts.sync_type,
    )


if __name__ == "__main__":
    sys.exit(direct_main(sys.argv[1:]))
