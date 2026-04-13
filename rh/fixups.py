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

"""Helper functions for attempting automated fixes."""

import sys
from typing import List

import rh.results
import rh.shell
import rh.terminal
import rh.utils


def attempt_fixes(
    projects_results: List[rh.results.ProjectResults], output_cls
) -> None:
    """Attempts to fix fixable results."""
    # Filter out any result that has a fixup.
    fixups = []
    for project_results in projects_results:
        fixups.extend(
            (project_results.workdir, x) for x in project_results.fixups
        )
    if not fixups:
        return

    if len(fixups) > 1:
        banner = f"Multiple fixups ({len(fixups)}) are available."
    else:
        banner = "Automated fixups are available."
    print(
        output_cls.COLOR.color(output_cls.COLOR.MAGENTA, banner),
        file=sys.stderr,
    )

    # If there's more than one fixup available, ask if they want to blindly run
    # them all, or prompt for them one-by-one.
    mode = "some"
    if len(fixups) > 1:
        while True:
            response = rh.terminal.str_prompt(
                "What would you like to do",
                ("Run (A)ll", "Run (S)ome", "(D)ry-run", "(N)othing [default]"),
            )
            if not response:
                print("", file=sys.stderr)
                return
            if response.startswith("a") or response.startswith("y"):
                mode = "all"
                break
            elif response.startswith("s"):
                mode = "some"
                break
            elif response.startswith("d"):
                mode = "dry-run"
                break
            elif response.startswith("n"):
                print("", file=sys.stderr)
                return

    # Walk all the fixups and run them one-by-one.
    for workdir, result in fixups:
        if mode == "some":
            if not rh.terminal.boolean_prompt(
                f"Run {result.hook} fixup for {result.commit}"
            ):
                continue

        cmd = tuple(result.fixup_cmd) + tuple(result.files)
        print(
            f"\n[{output_cls.RUNNING}] cd {rh.shell.quote(workdir)} && "
            f"{rh.shell.cmd_to_str(cmd)}",
            file=sys.stderr,
        )
        if mode == "dry-run":
            continue

        cmd_result = rh.utils.run(cmd, cwd=workdir, check=False)
        if cmd_result.returncode:
            print(
                f"[{output_cls.WARNING}] command exited "
                f"{cmd_result.returncode}",
                file=sys.stderr,
            )
        else:
            print(f"[{output_cls.PASSED}] great success", file=sys.stderr)

    print(
        f"\n[{output_cls.FIXUP}] Please amend & rebase your tree before "
        "attempting to upload again.\n",
        file=sys.stderr,
    )
