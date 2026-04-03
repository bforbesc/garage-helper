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


def _garageband_window_titles() -> list[str]:
    script = """
tell application "GarageBand"
  if (count of windows) is 0 then return ""
  return name of every window
end tell
"""
    result = run_applescript(script)
    if not result.get("ok"):
        return []
    raw = (result.get("stdout") or "").strip()
    if not raw:
        return []
    return [title.strip() for title in raw.split(",") if title.strip()]


def _has_real_project_window(window_titles: list[str]) -> bool:
    if not window_titles:
        return False
    return any(title.lower() != "choose a project" for title in window_titles)


def _wait_for_project_window(timeout_sec: float = 10.0) -> dict:
    deadline = time.monotonic() + max(1.0, timeout_sec)
    last_titles: list[str] = []
    while time.monotonic() < deadline:
        titles = _garageband_window_titles()
        if titles:
            last_titles = titles
        if _has_real_project_window(titles):
            return {"ok": True, "windows": titles}
        time.sleep(0.25)
    return {"ok": False, "windows": last_titles}


def _open_file_via_dialog(file_path: Path) -> dict:
    escaped_path = str(file_path).replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
set targetPath to "{escaped_path}"
tell application "GarageBand" to activate
delay 0.5
tell application "System Events"
  keystroke "o" using {{command down}}
  delay 0.8
  keystroke "g" using {{command down, shift down}}
  delay 0.4
  keystroke targetPath
  key code 36
  delay 0.5
  key code 36
end tell
"""
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
    focus_result = ensure_garageband_frontmost(timeout_ms=2500)
    proc = subprocess.run(
        ["open", "-a", "GarageBand", str(file_path)],
        capture_output=True,
        text=True,
    )
    verify_open = _wait_for_project_window(timeout_sec=12.0)
    fallback = {"ok": True, "skipped": True}
    if not verify_open.get("ok") and settings.allow_applescript:
        fallback = _open_file_via_dialog(file_path)
        verify_open = _wait_for_project_window(timeout_sec=12.0)
    front = get_frontmost_app()
    return {
        "ok": proc.returncode == 0 and bool(verify_open.get("ok")),
        "returncode": proc.returncode,
        "path": str(file_path.resolve()),
        "focus_result": focus_result,
        "verification": verify_open,
        "fallback_result": fallback,
        "frontmost_after": front.get("app", ""),
        "stderr": proc.stderr.strip(),
    }


def set_new_track_default(track_type: str) -> dict:
    """
    Configure GarageBand's new-track default type in macOS preferences.
    Known values include NTCSoftwareInstrument and NTCDrummer.
    """
    proc = subprocess.run(
        [
            "defaults",
            "write",
            "com.apple.garageband10",
            "NewTrackSheetDefaults",
            "-dict",
            "DefaultTrackType",
            track_type,
            "GroupID",
            "3",
            "ShowDetails",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "track_type": track_type,
        "stderr": proc.stderr.strip(),
    }


def add_new_track_from_menu(repeats: int = 1, delay_sec: float = 0.7) -> dict:
    focus = ensure_garageband_frontmost(timeout_ms=2500)
    if not focus.get("ok"):
        return {"ok": False, "error": "GarageBand focus not confirmed", "focus": focus}

    repeats = max(1, min(int(repeats), 8))
    script = f'''
tell application "GarageBand" to activate
delay 0.2
tell application "System Events"
  tell process "GarageBand"
    repeat {repeats} times
      click menu item "New Track…" of menu "Track" of menu bar 1
      delay {max(0.2, float(delay_sec))}
    end repeat
  end tell
end tell
'''
    result = run_applescript(script)
    windows = run_applescript('tell application "GarageBand" to if (count of windows) > 0 then return name of every window')
    return {
        "ok": bool(result.get("ok")),
        "repeats": repeats,
        "script_result": result,
        "windows": windows.get("stdout", ""),
    }


def add_drummer_tracks(repeats: int = 1) -> dict:
    default_set = set_new_track_default("NTCDrummer")
    if not default_set.get("ok"):
        return {"ok": False, "error": "Failed to set Drummer as default track type", "default_set": default_set}
    added = add_new_track_from_menu(repeats=repeats)
    return {
        "ok": bool(default_set.get("ok")) and bool(added.get("ok")),
        "default_set": default_set,
        "added": added,
    }
