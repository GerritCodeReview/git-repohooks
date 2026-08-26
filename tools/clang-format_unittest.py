#!/usr/bin/env python3
# Copyright 2022 The Android Open Source Project
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

"""Unittests for clang-format."""

import contextlib
from pathlib import Path
import sys
import tempfile
import unittest


THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR.parent))

# We have to import our local modules after the sys.path tweak.  We can't use
# relative imports because this is an executable program, not a module.
# pylint: disable=wrong-import-position,import-error
import rh.utils


CLANG_FORMAT = THIS_DIR / "clang-format.py"


@contextlib.contextmanager
def git_clang_format(data: str):
    """Create a fake git-clang-format script."""
    with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
        tempdir = Path(tempdir)
        script = tempdir / "git-clang-format-fake.sh"
        script.write_text(f"#!/bin/sh\n{data}", encoding="utf-8")
        script.chmod(0o755)
        yield script


def run_clang_format(script, args, **kwargs):
    """Helper to run clang-format.py with fake git-clang-format script."""
    kwargs.setdefault("capture_output", True)
    return rh.utils.run(
        [CLANG_FORMAT, "--git-clang-format", script] + args, **kwargs
    )


class GitClangFormatExit(unittest.TestCase):
    """Test git-clang-format parsing."""

    def test_diff_exit_0_no_output(self):
        """Test exit 0 w/no output."""
        with git_clang_format("exit 0") as script:
            result = run_clang_format(script, ["--working-tree"])
            self.assertEqual(result.stdout, "")

    def test_diff_exit_0_stderr(self):
        """Test exit 0 w/stderr output."""
        with git_clang_format("echo bad >&2; exit 0") as script:
            with self.assertRaises(rh.utils.CalledProcessError) as e:
                run_clang_format(script, ["--working-tree"])
            self.assertIn("clang-format failed", e.exception.stderr)

    def test_diff_exit_1_no_output(self):
        """Test exit 1 w/no output."""
        with git_clang_format("exit 1") as script:
            result = run_clang_format(script, ["--working-tree"])
            self.assertEqual(result.stdout, "")

    def test_diff_exit_1_output(self):
        """Test exit 1 with output."""
        with git_clang_format("echo bad; exit 1") as script:
            with self.assertRaises(rh.utils.CalledProcessError) as e:
                run_clang_format(script, ["--working-tree"])
            self.assertIn("clang-format failed", e.exception.stderr)

    def test_diff_exit_1_stderr(self):
        """Test exit 1 w/stderr."""
        with git_clang_format("echo bad >&2; exit 1") as script:
            with self.assertRaises(rh.utils.CalledProcessError) as e:
                run_clang_format(script, ["--working-tree"])
            self.assertIn("clang-format failed", e.exception.stderr)

    def test_diff_exit_2(self):
        """Test exit 2."""
        with git_clang_format("exit 2") as script:
            with self.assertRaises(rh.utils.CalledProcessError) as e:
                run_clang_format(script, ["--working-tree"])
            self.assertIn("clang-format failed", e.exception.stderr)

    def test_fix_exit_1_output(self):
        """Test fix with incorrect patch syntax."""
        with git_clang_format("echo bad patch; exit 1") as script:
            with self.assertRaises(rh.utils.CalledProcessError) as e:
                run_clang_format(script, ["--working-tree", "--fix"])
            self.assertIn(
                "Error: Unable to automatically fix things", e.exception.stderr
            )


@contextlib.contextmanager
def fake_clang_format(data: str):
    """Create a fake clang-format script."""
    with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
        tempdir = Path(tempdir)
        script = tempdir / "clang-format-fake.sh"
        script.write_text(f"#!/bin/sh\n{data}", encoding="utf-8")
        script.chmod(0o755)
        yield script


def run_whole_file_clang_format(script, args, **kwargs):
    """Helper to run clang-format.py --whole-file with fake script."""
    kwargs.setdefault("capture_output", True)
    return rh.utils.run(
        [CLANG_FORMAT, "--clang-format", script, "--whole-file"] + args,
        **kwargs,
    )


class WholeFileClangFormatTest(unittest.TestCase):
    """Test whole-file clang-format execution."""

    def test_clean_file(self):
        """Test exit 0 when file is already formatted."""
        with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
            tempdir = Path(tempdir)
            cpp_file = tempdir / "test.cpp"
            cpp_file.write_text("int main() {}\n", encoding="utf-8")
            with fake_clang_format("cat") as script:
                result = run_whole_file_clang_format(
                    script, ["--working-tree", "test.cpp"], cwd=tempdir
                )
                self.assertEqual(result.stdout, "")

    def test_dirty_file(self):
        """Test exit 1 when file has formatting errors."""
        with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
            tempdir = Path(tempdir)
            cpp_file = tempdir / "test.cpp"
            cpp_file.write_text("int   main()   {}\n", encoding="utf-8")
            with fake_clang_format("echo 'int main() {}'") as script:
                with self.assertRaises(rh.utils.CalledProcessError) as e:
                    run_whole_file_clang_format(
                        script, ["--working-tree", "test.cpp"], cwd=tempdir
                    )
                self.assertIn(
                    "The following files have formatting errors",
                    e.exception.stdout,
                )
                self.assertIn("test.cpp", e.exception.stdout)

    def test_fix(self):
        """Test --fix automatically updates the file."""
        with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
            tempdir = Path(tempdir)
            rh.utils.run(["git", "init"], cwd=tempdir, capture_output=True)
            cpp_file = tempdir / "test.cpp"
            cpp_file.write_text("int   main()   {}\n", encoding="utf-8")
            rh.utils.run(
                ["git", "add", "test.cpp"], cwd=tempdir, capture_output=True
            )
            rh.utils.run(
                ["git", "commit", "-m", "init"],
                cwd=tempdir,
                capture_output=True,
            )
            with fake_clang_format("echo 'int main() {}'") as script:
                result = run_whole_file_clang_format(
                    script, ["--working-tree", "--fix", "test.cpp"], cwd=tempdir
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    cpp_file.read_text(encoding="utf-8"), "int main() {}\n"
                )

    def test_extensions_filter(self):
        """Test that files not matching extensions are skipped."""
        with tempfile.TemporaryDirectory(prefix="repohooks-tests") as tempdir:
            tempdir = Path(tempdir)
            md_file = tempdir / "test.md"
            md_file.write_text("some markdown\n", encoding="utf-8")
            with fake_clang_format("echo 'reformatted'") as script:
                result = run_whole_file_clang_format(
                    script,
                    ["--working-tree", "--extensions", "c,cpp", "test.md"],
                    cwd=tempdir,
                )
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
