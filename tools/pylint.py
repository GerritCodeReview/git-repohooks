#!/usr/bin/env python3
# Copyright 2016 The Android Open Source Project
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

"""Wrapper to run pylint with the right settings."""

import argparse
import errno
import os
import sys
import subprocess
from typing import Dict, List, Optional, Set


# This script is run by repohooks users.
# See README.md for what version we may require.
assert (sys.version_info.major, sys.version_info.minor) >= (
    3,
    6,
), f"Python 3.6 or newer is required; found {sys.version}"


DEFAULT_PYLINTRC_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "pylintrc"
)


def run_lint(
    pylint: str,
    unknown: Optional[List[str]],
    files: Optional[List[str]],
    init_hook: str,
    pylintrc: Optional[str] = None,
) -> bool:
    """Run lint command.

    Upon error the stdout from pylint will be dumped to stdout and
    False will be returned.
    """
    cmd = [pylint]

    if not files:
        # No files to analyze for this pylintrc file.
        return True

    if pylintrc:
        cmd += ["--rcfile", pylintrc]

    files.sort()
    cmd += unknown + files

    if init_hook:
        cmd += ["--init-hook", init_hook]

    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, text=True, check=False
        )
    except OSError as e:
        if e.errno == errno.ENOENT:
            print(f"{__file__}: unable to run `{cmd[0]}`: {e}", file=sys.stderr)
            print(
                f"{__file__}: Try installing pylint: sudo apt-get install "
                f"{os.path.basename(cmd[0])}",
                file=sys.stderr,
            )
            return False

        raise

    if result.returncode:
        print(f"{__file__}: Using pylintrc: {pylintrc}")
        print(result.stdout)
        return False

    return True


def find_parent_dirs_with_pylintrc(
    leafdir: str, pylintrc_map: Dict[str, Set[str]]
) -> None:
    """Find all dirs containing a pylintrc between root dir and leafdir."""

    # Find all pylintrc files, store the path. The path must end with '/'
    # to make sure that string compare can be used to compare with full
    # path to python files later.

    rootdir = os.path.abspath(".") + os.sep
    key = os.path.abspath(leafdir) + os.sep

    if not key.startswith(rootdir):
        sys.exit(
            f"{__file__}: The search directory {key} is outside the "
            f"repo dir {rootdir}"
        )

    while rootdir != key:
        # This subdirectory has already been handled, skip it.
        if key in pylintrc_map:
            break

        if os.path.exists(os.path.join(key, "pylintrc")):
            pylintrc_map.setdefault(key, set())
            break

        # Go up one directory.
        key = os.path.abspath(os.path.join(key, os.pardir)) + os.sep


def map_pyfiles_to_pylintrc(files: List[str]) -> Dict[str, Set[str]]:
    """Map all python files to a pylintrc file.

    Generate dictionary with pylintrc-file dirnames (including trailing /)
    as key containing sets with corresponding python files.
    """

    pylintrc_map = {}
    # We assume pylint is running in the top directory of the project,
    # so load the pylintrc file from there if it is available.
    pylintrc = os.path.abspath("pylintrc")
    if not os.path.exists(pylintrc):
        pylintrc = DEFAULT_PYLINTRC_PATH
        # If we pass a non-existent rcfile to pylint, it'll happily ignore
        # it.
        assert os.path.exists(pylintrc), f"Could not find {pylintrc}"
    # Always add top directory, either there is a pylintrc or fallback to
    # default.
    key = os.path.abspath(".") + os.sep
    pylintrc_map[key] = set()

    search_dirs = {os.path.dirname(x) for x in files}
    for search_dir in search_dirs:
        find_parent_dirs_with_pylintrc(search_dir, pylintrc_map)

    # List of directories where pylintrc files are stored, most
    # specific path first.
    rc_dir_names = sorted(pylintrc_map, reverse=True)
    # Map all python files to a pylintrc file.
    for f in files:
        f_full = os.path.abspath(f)
        for rc_dir in rc_dir_names:
            # The pylintrc map keys always have trailing /.
            if f_full.startswith(rc_dir):
                pylintrc_map[rc_dir].add(f)
                break
        else:
            sys.exit(f"{__file__}: Failed to map file {f} to a pylintrc file.")

    return pylintrc_map


def get_parser():
    """Return a command line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-hook", help="Init hook commands to run.")
    parser.add_argument(
        "--executable-path",
        default="pylint",
        help="The path of the pylint executable.",
    )
    parser.add_argument(
        "--no-rcfile",
        dest="use_default_conf",
        help="Specify to use the executable's default configuration.",
        action="store_true",
    )
    parser.add_argument("files", nargs="+")
    return parser


def main(argv):
    """The main entry."""
    parser = get_parser()
    opts, unknown = parser.parse_known_args(argv)
    ret = 0

    pylint = opts.executable_path
    if not opts.use_default_conf:
        pylintrc_map = map_pyfiles_to_pylintrc(opts.files)
        first = True
        for rc_dir, files in sorted(pylintrc_map.items()):
            pylintrc = os.path.join(rc_dir, "pylintrc")
            if first:
                first = False
                assert os.path.abspath(rc_dir) == os.path.abspath(
                    "."
                ), f"{__file__}: pylintrc in top dir not first in list"
                if not os.path.exists(pylintrc):
                    pylintrc = DEFAULT_PYLINTRC_PATH
            if not run_lint(
                pylint, unknown, sorted(files), opts.init_hook, pylintrc
            ):
                ret = 1
    # Not using rc files, pylint default behaviour.
    elif not run_lint(pylint, unknown, sorted(opts.files), opts.init_hook):
        ret = 1

    return ret


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
