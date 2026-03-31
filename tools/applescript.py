from __future__ import annotations

import subprocess
import time
from pathlib import Path

from config import settings


def run_applescript(script: str) -> dict:
    if not settings.allow_applescript:
        return {"ok": False, "error": "AppleScript disabled. Set ALLOW_APPLESCRIPT=true to enable."}
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "AppleScript timed out"}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def launch_garageband() -> dict:
    script = 'tell application "GarageBand" to activate'
    return run_applescript(script)


def get_frontmost_app() -> dict:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    result = run_applescript(script)
    if not result.get("ok"):
        return result
    return {"ok": True, "app": result.get("stdout", "")}


def ensure_garageband_frontmost(timeout_ms: int = 1500) -> dict:
    if not settings.allow_applescript:
        return {"ok": True, "skipped": True, "reason": "AppleScript disabled; focus check skipped"}
    launch_result = launch_garageband()
    deadline = time.monotonic() + max(200, int(timeout_ms)) / 1000
    last_app = ""
    last_error = ""
    while time.monotonic() < deadline:
        front = get_frontmost_app()
        if front.get("ok"):
            last_app = front.get("app", "")
            if last_app.lower() == "garageband":
                return {"ok": True, "frontmost_app": last_app, "launch_result": launch_result}
        else:
            last_error = front.get("stderr") or front.get("error", "")
        time.sleep(0.1)
    return {
        "ok": False,
        "error": "GarageBand focus not confirmed.",
        "frontmost_app": last_app,
        "focus_error": last_error,
        "launch_result": launch_result,
    }


def new_garageband_project_dialog() -> dict:
    focus = ensure_garageband_frontmost(timeout_ms=1500)
    if not focus.get("ok"):
        return {"ok": False, "error": "Cannot open new project dialog without GarageBand focus.", "focus": focus}
    script = """
tell application "System Events"
  keystroke "n" using {command down}
end tell
"""
    result = run_applescript(script)
    front = get_frontmost_app()
    return {
        "ok": bool(result.get("ok")) and bool(front.get("ok")) and front.get("app", "").lower() == "garageband",
        "action": "new_project_dialog",
        "applescript_result": result,
        "frontmost_after": front.get("app", ""),
    }


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
