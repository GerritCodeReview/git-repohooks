#!/usr/bin/env python3
# Copyright (C) 2026 The Android Open Source Project
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

"""Unittests for the trace module."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
sys.path.insert(0, str(THIS_DIR.parent))

# pylint: disable=wrong-import-position
import rh.trace


class TraceTest(unittest.TestCase):
    """Test Git Trace2 event emission in rh.trace."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.trace_file = os.path.join(self.tempdir, "trace.json")
        os.environ["GIT_TRACE2_EVENT"] = self.trace_file
        os.environ["GIT_TRACE2_PARENT_SID"] = "test-repo-sid"

    def tearDown(self):
        os.environ.pop("GIT_TRACE2_EVENT", None)
        os.environ.pop("GIT_TRACE2_PARENT_SID", None)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_record_region_emits_enter_and_leave(self):
        """Verify record_region writes region_enter and region_leave events."""
        with rh.trace.record_region("repohook", "ktfmt", msg="commit-123"):
            pass

        with open(self.trace_file, "r", encoding="utf-8") as fp:
            events = [json.loads(line) for line in fp if line.strip()]

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event"], "region_enter")
        self.assertEqual(events[0]["category"], "repohook")
        self.assertEqual(events[0]["label"], "ktfmt")
        self.assertEqual(events[0]["msg"], "commit-123")
        self.assertTrue(
            events[0]["sid"].startswith("test-repo-sid/repohooks-P")
        )

        self.assertEqual(events[1]["event"], "region_leave")
        self.assertEqual(events[1]["category"], "repohook")
        self.assertEqual(events[1]["label"], "ktfmt")
        self.assertIn("relative_time_us", events[1])

    def test_disabled_tracing_is_silent(self):
        """Verify nothing is written when GIT_TRACE2_EVENT is unset."""
        os.environ.pop("GIT_TRACE2_EVENT", None)
        with rh.trace.record_region("repohook", "ktfmt"):
            pass
        self.assertFalse(os.path.exists(self.trace_file))


if __name__ == "__main__":
    unittest.main()
