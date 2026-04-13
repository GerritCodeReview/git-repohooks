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

        with self.assertRaises(SystemExit):
            rh.fixups.attempt_fixes([project_results], self.output_cls)

        mock_prompt.assert_called_once()
        mock_run.assert_not_called()


    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.git.get_commit_desc')
    @mock.patch('rh.utils.run')
    def test_attempt_fixes_commit_fixups(self, mock_run, mock_get_commit_desc, mock_boolean_prompt):
        """Test attempt_fixes with commit_fixups=True."""
        mock_boolean_prompt.return_value = True
        # Mock run for:
        # 1. The fixup command itself.
        # 2. git add
        # 3. git diff --cached --quiet (returns 1 to indicate changes!)
        # 4. git commit

        def side_effect(cmd, cwd=None, check=True):
            if cmd[0] == 'fix_cmd':
                return mock.Mock(returncode=0)
            elif cmd[0:2] == ['git', 'add']:
                return mock.Mock(returncode=0)
            elif cmd[0:3] == ['git', 'diff', '--cached']:
                return mock.Mock(returncode=1)  # Changes present!
            elif cmd[0:2] == ['git', 'commit']:
                return mock.Mock(returncode=0)
            return mock.Mock(returncode=0)

        mock_run.side_effect = side_effect
        mock_get_commit_desc.return_value = "Subject line\n\nBody"

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
            rh.fixups.attempt_fixes([project_results], self.output_cls, commit_fixups=True)

        self.assertTrue(mock_run.called)
        mock_run.assert_any_call(['git', 'add', '--', 'file1.py'], cwd='/tmp/test_project')
        mock_run.assert_any_call(['git', 'commit', '-m', 'fixup! Subject line', '--', 'file1.py'], cwd='/tmp/test_project')


    @mock.patch('rh.terminal.boolean_prompt')
    @mock.patch('rh.utils.run')
    def test_attempt_fixes_autosquash(self, mock_run, mock_boolean_prompt):
        """Test attempt_fixes with autosquash=True."""
        mock_boolean_prompt.return_value = True
        # Mock run for:
        # 1. git log (returns a fixup! commit)
        # 2. git rebase

        def side_effect(cmd, cwd=None, capture_output=False, env=None, check=True):
            if cmd[0:2] == ['git', 'log']:
                return mock.Mock(stdout="abc1234 fixup! Subject line\n")
            elif cmd[0:2] == ['git', 'rebase']:
                return mock.Mock(returncode=0)
            return mock.Mock(returncode=0)

        mock_run.side_effect = side_effect

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
            rh.fixups.attempt_fixes([project_results], self.output_cls, autosquash=True)

        self.assertTrue(mock_run.called)
        mock_run.assert_any_call(['git', 'log', '--oneline', '@{u}..HEAD'], cwd='/tmp/test_project', capture_output=True)
        mock_run.assert_any_call(['git', 'rebase', '-i', '--autosquash', '@{u}'], cwd='/tmp/test_project', env=mock.ANY)


if __name__ == '__main__':
    unittest.main()
