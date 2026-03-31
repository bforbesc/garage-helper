from __future__ import annotations

import subprocess
from pathlib import Path

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


def open_file_in_garageband(path: str) -> dict:
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}
    proc = subprocess.run(
        ["open", "-a", "GarageBand", str(file_path)],
        capture_output=True,
        text=True,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "path": str(file_path.resolve()),
        "stderr": proc.stderr.strip(),
    }
