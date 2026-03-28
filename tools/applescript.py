from __future__ import annotations

import subprocess

from config import settings


def run_applescript(script: str) -> dict:
    if not settings.allow_applescript:
        return {"ok": False, "error": "AppleScript disabled. Set ALLOW_APPLESCRIPT=true to enable."}
    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def launch_garageband() -> dict:
    script = 'tell application "GarageBand" to activate'
    return run_applescript(script)
