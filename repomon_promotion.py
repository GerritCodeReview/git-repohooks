#!/usr/bin/env python3
"""
Post-sync hook to promote Repomon on slow syncs.
"""
import argparse
import os
from pathlib import Path
import select
import subprocess
import sys
import time

# Define threshold in seconds (e.g., 12 minutes = 720 seconds)
SLOW_SYNC_THRESHOLD_SEC = 12 * 60
# Forced update to ensure threshold is updated on Gerrit

# 24 hours in seconds
ESTABLISHED_WORKSPACE_THRESHOLD_SEC = 24 * 60 * 60


def is_established_workspace(repo_root):
    """Infers if the workspace is established based on .repo age."""
    repo_dir = os.path.join(repo_root, ".repo")

    # Try to get birth time using stat -c %W (Linux specific)
    try:
        output = subprocess.check_output(["stat", "-c", "%W", repo_dir], text=True, timeout=5).strip()
        birth_time = int(output)
        if birth_time > 0:
            current_time = time.time()
            return (current_time - birth_time) > ESTABLISHED_WORKSPACE_THRESHOLD_SEC
    except Exception:
        # Fallback to manifest.xml modification time if stat fails
        pass

    manifest_link = os.path.join(repo_dir, "manifest.xml")
    if not os.path.exists(manifest_link):
        return False

    manifest_mtime = os.path.getmtime(manifest_link)
    current_time = time.time()

    return (current_time - manifest_mtime) > ESTABLISHED_WORKSPACE_THRESHOLD_SEC


def main(repo_topdir=None, **kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-duration-seconds", type=float)
    parser.add_argument("--repo-topdir")
    args, _ = parser.parse_known_args()

    sync_duration = (
        kwargs.get("sync_duration_seconds") or args.sync_duration_seconds
    )
    repo_root = repo_topdir or args.repo_topdir or os.getcwd()

    # Validate repo_root
    if not os.path.isdir(repo_root):
        print(f"Error: {repo_root} is not a directory.")
        return 1
    if not os.path.isdir(os.path.join(repo_root, ".repo")):
        print(f"Error: {repo_root} is not a repo workspace root (missing .repo).")
        return 1

    # 1. Check if Repomon is already present
    repomon_dir = os.path.expanduser("~/.repomon")
    if os.path.exists(repomon_dir):
        return 0

    # 2. Check if workspace is established
    if not is_established_workspace(repo_root):
        return 0

    # 3. Check if sync was slow
    if sync_duration and sync_duration > SLOW_SYNC_THRESHOLD_SEC:
        mins = int(sync_duration / 60)
        print("\n" + "=" * 70)
        print(f"Notice: Your syncs are taking too long ({mins} minutes).")
        print("Do you want to install Repomon (go/repo-mon) to make it faster? (Y/n): ", end="", flush=True)

        try:
            rlist, _, _ = select.select([sys.stdin], [], [], 60)
            if rlist:
                response = sys.stdin.readline().strip().lower()
                if response in ("y", "yes", ""):
                    curl_url = "https://googleplex-android.googlesource.com/platform/vendor/google/tools/+/refs/heads/main/repo_utils/install.sh?format=TEXT"
                    try:
                        curl_proc = subprocess.Popen(
                            ["gob-curl", "-s", curl_url],
                            stdout=subprocess.PIPE
                        )
                        base64_proc = subprocess.Popen(
                            ["base64", "--decode"],
                            stdin=curl_proc.stdout,
                            stdout=subprocess.PIPE
                        )
                        bash_proc = subprocess.Popen(
                            ["bash", "-s", "--", "-y", "-d", repo_root],
                            stdin=base64_proc.stdout
                        )

                        curl_proc.stdout.close()
                        base64_proc.stdout.close()

                        try:
                            bash_proc.communicate(timeout=300)
                        except subprocess.TimeoutExpired:
                            print("\nInstallation timed out. Terminating processes...")
                            bash_proc.kill()
                            base64_proc.kill()
                            curl_proc.kill()
                            bash_proc.communicate()
                            print("Installation aborted.")
                            return 1

                        curl_proc.wait()
                        base64_proc.wait()

                        if (
                            curl_proc.returncode == 0
                            and base64_proc.returncode == 0
                            and bash_proc.returncode == 0
                        ):
                            print("Installation completed successfully.")
                        else:
                            print("Installation failed.")
                            if curl_proc.returncode != 0:
                                print(f"  gob-curl failed with exit code {curl_proc.returncode}")
                            if base64_proc.returncode != 0:
                                print(f"  base64 failed with exit code {base64_proc.returncode}")
                            if bash_proc.returncode != 0:
                                print(f"  bash failed with exit code {bash_proc.returncode}")
                    except Exception as e:
                        print(f"Installation failed: {e}")

                else:
                    print("Skipping installation.")
            else:
                print("\nTimeout. Skipping installation.")
        except KeyboardInterrupt:
            print("\nSkipping installation (cancelled by user).")

        print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
