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

"""Unit tests for rh.trace."""

import json
import os
import tempfile
import unittest

import rh.trace


class TraceTest(unittest.TestCase):
    """Test Git Trace2 event emission in rh.trace."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.tmpfile.close()
        os.environ["GIT_TRACE2_EVENT"] = self.tmpfile.name
        os.environ["GIT_TRACE2_PARENT_SID"] = "test-repo-sid"

    def tearDown(self):
        os.environ.pop("GIT_TRACE2_EVENT", None)
        os.environ.pop("GIT_TRACE2_PARENT_SID", None)
        if os.path.exists(self.tmpfile.name):
            os.remove(self.tmpfile.name)

    def test_record_region_emits_enter_and_leave(self):
        """Verify record_region writes region_enter and region_leave events."""
        with rh.trace.record_region("repohook", "ktfmt", msg="commit-123"):
            pass

        with open(self.tmpfile.name, "r", encoding="utf-8") as fp:
            lines = [json.loads(line) for line in fp if line.strip()]

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["event"], "region_enter")
        self.assertEqual(lines[0]["category"], "repohook")
        self.assertEqual(lines[0]["label"], "ktfmt")
        self.assertEqual(lines[0]["msg"], "commit-123")
        self.assertTrue(lines[0]["sid"].startswith("test-repo-sid/repohooks-P"))

        self.assertEqual(lines[1]["event"], "region_leave")
        self.assertEqual(lines[1]["category"], "repohook")
        self.assertEqual(lines[1]["label"], "ktfmt")
        self.assertIn("relative_time_us", lines[1])

    def test_disabled_tracing_is_silent(self):
        """Verify nothing is written when GIT_TRACE2_EVENT is unset."""
        os.environ.pop("GIT_TRACE2_EVENT", None)
        with rh.trace.record_region("repohook", "ktfmt"):
            pass
        self.assertEqual(os.path.getsize(self.tmpfile.name), 0)


if __name__ == "__main__":
    unittest.main()
