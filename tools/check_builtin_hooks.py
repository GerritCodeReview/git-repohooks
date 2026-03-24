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

"""Check that all hooks in GLOBAL-PREUPLOAD.cfg are defined in hooks.py."""

import argparse
import os
import sys

# Add the repohooks dir to sys.path so we can import rh.
_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if sys.path[0] != _path:
    sys.path.insert(0, _path)
del _path

# pylint: disable=wrong-import-position
import rh.config
import rh.hooks

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='*', help='Files to check.')
    args = parser.parse_args(argv)

    found_error = False
    for path in args.files:
        if os.path.basename(path) != 'GLOBAL-PREUPLOAD.cfg':
            continue

        try:
            # This will trigger the validation in rh.config.PreUploadConfig._validate.
            rh.config.GlobalPreUploadFile(path)
        except Exception as e:
            print(f'Error validating {path}:', file=sys.stderr)
            print(f'{e}', file=sys.stderr)
            print('\nIf you are adding a new builtin hook or tool, ensure its implementation '
                  'is merged in the repohooks project FIRST.', file=sys.stderr)
            found_error = True

    if found_error:
        sys.exit(1)

if __name__ == '__main__':
    main(sys.argv[1:])
