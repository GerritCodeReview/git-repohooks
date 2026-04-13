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

"""Unittests for the fixups module."""

from pathlib import Path
import sys
import unittest
from unittest import mock

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR.parent))

# We have to import our local modules after the sys.path tweak.  We can't use
# relative imports because this is an executable program, not a module.
# pylint: disable=wrong-import-position
import rh.results
import rh.fixups


class AttemptFixesTests(unittest.TestCase):
    """Tests for attempt_fixes function."""

    def setUp(self):
        self.output_cls = mock.Mock()
        self.output_cls.COLOR = mock.Mock()
        self.output_cls.COLOR.color.side_effect = lambda c, s: s
        self.output_cls.COLOR.MAGENTA = 'magenta'
        self.output_cls.RUNNING = 'running'
        self.output_cls.PASSED = 'passed'
        self.output_cls.WARNING = 'warning'
        self.output_cls.FIXUP = 'fixup'

    @mock.patch('rh.terminal.str_prompt')
    @mock.patch('rh.utils.run')
    def test_attempt_fixes_all(self, mock_run, mock_prompt):
        """Test attempt_fixes with 'All' mode."""
        mock_prompt.return_value = 'a'
        mock_run.return_value = mock.Mock(returncode=0)

        hook_result = rh.results.HookResult(
            hook='test_hook',
            project='test_project',
            commit='HEAD',
            error='error',
            files=['file1.py'],
            fixup_cmd=['fix_cmd'],
        )
        hook_result2 = rh.results.HookResult(
            hook='test_hook2',
            project='test_project',
            commit='HEAD',
            error='error2',
            files=['file2.py'],
            fixup_cmd=['fix_cmd2'],
        )
        project_results = rh.results.ProjectResults(
            project='test_project',
            workdir='/tmp/test_project',
            results=[hook_result, hook_result2],
        )

        # We expect sys.exit(1) to be called because fixes are applied!
        with self.assertRaises(SystemExit):
            rh.fixups.attempt_fixes([project_results], self.output_cls)

        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_any_call(('fix_cmd', 'file1.py'), cwd='/tmp/test_project', check=False)
        mock_run.assert_any_call(('fix_cmd2', 'file2.py'), cwd='/tmp/test_project', check=False)

    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.utils.run')
    def test_attempt_fixes_some_yes(self, mock_run, mock_prompt):
        """Test attempt_fixes with 'Some' mode and user says Yes."""
        mock_prompt.return_value = True
        mock_run.return_value = mock.Mock(returncode=0)

        hook_result = rh.results.HookResult(
            hook='test_hook',
            project='test_project',
            commit='HEAD',
            error='error',
            files=['file1.py'],
            fixup_cmd=['fix_cmd'],
        )
        project_results = rh.results.ProjectResults(
            project='test_project',
            workdir='/tmp/test_project',
            results=[hook_result],
        )

        with self.assertRaises(SystemExit):
            rh.fixups.attempt_fixes([project_results], self.output_cls)

        mock_prompt.assert_called_once()
        mock_run.assert_called_once_with(('fix_cmd', 'file1.py'), cwd='/tmp/test_project', check=False)

    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.utils.run')
    def test_attempt_fixes_some_no(self, mock_run, mock_prompt):
        """Test attempt_fixes with 'Some' mode and user says No."""
        mock_prompt.return_value = False

        hook_result = rh.results.HookResult(
            hook='test_hook',
            project='test_project',
            commit='HEAD',
            error='error',
            files=['file1.py'],
            fixup_cmd=['fix_cmd'],
        )
        project_results = rh.results.ProjectResults(
            project='test_project',
            workdir='/tmp/test_project',
            results=[hook_result],
        )

        rh.fixups.attempt_fixes([project_results], self.output_cls)

        mock_prompt.assert_called_once()
        mock_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
