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

"""Check that preupload configuration files are well-formed."""

import argparse
import os
from pathlib import Path
import sys
from typing import List

# Add the repohooks dir to sys.path so we can import rh.
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR.parent))

# pylint: disable=wrong-import-position
import rh.config


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="Files to check.")
    opts = parser.parse_args(argv)

    found_error = False
    for path in opts.files:
        try:
            # This will trigger the validation in
            # rh.config.PreUploadConfig._validate.
            if path.name == rh.config.GlobalPreUploadFile.FILENAME:
                rh.config.GlobalPreUploadFile(path)
            else:
                rh.config.PreUploadFile(path)
        except rh.config.ValidationError as e:
            print(f"Error validating {path}:", file=sys.stderr)
            print(f"{e}", file=sys.stderr)
            print(
                "\nIf you are adding a new builtin hook or tool, ensure its "
                "implementation is merged in the repohooks project FIRST.",
                file=sys.stderr,
            )
            found_error = True

    return 1 if found_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
