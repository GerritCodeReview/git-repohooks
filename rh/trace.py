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

"""Git Trace2 telemetry event logging for repohooks.

When GIT_TRACE2_EVENT is set in the environment, this module emits JSON Trace2
events (conforming to Git's trace2 event API) so that local repohooks execution
and per-linter latency can be ingested by git-trace-daemon and Plx dashboards.
"""

import contextlib
import datetime
import json
import os
import socket
import sys
from typing import Any, Dict, Optional

import rh.git
import rh.utils


_START_TIME = datetime.datetime.now(datetime.timezone.utc)


def get_trace2_target() -> Optional[str]:
    """Return the configured Git Trace2 event target, or None if disabled."""
    target = os.environ.get("GIT_TRACE2_EVENT", "").strip()
    return target or None


def get_sid() -> str:
    """Return the hierarchical Trace2 session ID for this repohooks process."""
    parent = os.environ.get(
        "GIT_TRACE2_PARENT_SID",
        os.environ.get("GIT_TRACE2_EVENT_SID", ""),
    ).strip()
    pid_sid = f"repohooks-P{os.getpid():08x}"
    return f"{parent}/{pid_sid}" if parent else pid_sid


def _get_utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp string required by Git Trace2."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _get_elapsed_seconds() -> float:
    """Return float seconds elapsed since rh.trace module initialization."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - _START_TIME).total_seconds()


def _get_exe_version() -> str:
    """Return repohooks git commit or version string for the version event."""
    try:
        return rh.git.get_commit_for_ref("HEAD")
    except (OSError, ValueError, rh.utils.CalledProcessError):
        return "repohooks"


def _write_trace2_event(event_dict: Dict[str, Any]) -> None:
    """Write a formatted JSON Trace2 event to the configured target."""
    target = get_trace2_target()
    if not target:
        return

    event_dict.setdefault("sid", get_sid())
    event_dict.setdefault("thread", "main")
    event_dict.setdefault("time", _get_utc_timestamp())

    payload = (json.dumps(event_dict) + "\n").encode("utf-8")

    try:
        if target.startswith("af_unix:"):
            sock_type = (
                socket.SOCK_DGRAM
                if target.startswith("af_unix:dgram:")
                else socket.SOCK_STREAM
            )
            sock_path = target.split(":", 2)[-1]
            with socket.socket(socket.AF_UNIX, sock_type) as sock:
                if sock_type == socket.SOCK_STREAM:
                    sock.settimeout(0.5)
                    sock.connect(sock_path)
                    sock.sendall(payload)
                else:
                    sock.sendto(payload, sock_path)
        else:
            with open(target, "ab") as fp:
                fp.write(payload)
    except OSError:
        # Silently ignore write errors so tracing never breaks hooks.
        pass


def start_session() -> None:
    """Emit Trace2 version and start events when repohooks begins execution."""
    if not get_trace2_target():
        return

    _write_trace2_event(
        {
            "event": "version",
            "evt": "2",
            "exe": _get_exe_version(),
        }
    )
    _write_trace2_event(
        {
            "event": "start",
            "t_abs": _get_elapsed_seconds(),
            "argv": sys.argv,
        }
    )


def exit_session(return_code: int = 0) -> None:
    """Emit Trace2 exit event when repohooks finishes execution."""
    if not get_trace2_target():
        return

    _write_trace2_event(
        {
            "event": "exit",
            "t_abs": _get_elapsed_seconds(),
            "code": return_code,
        }
    )


@contextlib.contextmanager
def record_region(category: str, label: str, msg: str = ""):
    """Context manager to emit region_enter and region_leave Trace2 events."""
    if not get_trace2_target():
        # Must yield once to satisfy contextmanager protocol when disabled.
        yield
        return

    start_time = datetime.datetime.now(datetime.timezone.utc)
    enter_event = {
        "event": "region_enter",
        "category": category,
        "label": label,
        "nesting_level": 1,
    }
    if msg:
        enter_event["msg"] = msg
    _write_trace2_event(enter_event)

    try:
        yield
    finally:
        end_time = datetime.datetime.now(datetime.timezone.utc)
        elapsed_us = int((end_time - start_time).total_seconds() * 1000000)
        leave_event = {
            "event": "region_leave",
            "category": category,
            "label": label,
            "nesting_level": 1,
            "relative_time_us": elapsed_us,
        }
        if msg:
            leave_event["msg"] = msg
        _write_trace2_event(leave_event)
