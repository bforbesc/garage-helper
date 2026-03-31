from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import mss
import mss.tools
import pyautogui

from config import settings

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

GARAGEBAND_SHORTCUTS = {
    "play_pause": "space",
    "new_track_dialog": "command+option+n",
    "open_editor": "e",
    "toggle_library": "y",
    "toggle_smart_controls": "b",
    "toggle_cycle": "c",
    "toggle_metronome": "k",
    "undo": "command+z",
    "redo": "command+shift+z",
    "duplicate_region": "command+r",
    "split_at_playhead": "command+t",
    "save_project": "command+s",
}


def ensure_enabled() -> None:
    if not settings.enable_computer_control:
        raise PermissionError("Computer control disabled. Set ENABLE_COMPUTER_CONTROL=true to allow UI actions.")


def _ensure_screenshots_dir() -> Path:
    path = Path(settings.screenshots_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshot(include_base64: bool = False) -> dict:
    out_dir = _ensure_screenshots_dir()
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    path = out_dir / filename
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    if include_base64:
        import base64  # local import to avoid paying cost on every screenshot call

        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"path": str(path), "base64_png": b64}
    return {"path": str(path)}


def click(x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
    ensure_enabled()
    pyautogui.click(x=x, y=y, button=button, clicks=clicks)
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "click", "x": x, "y": y, "button": button, "clicks": clicks}


def type_text(text: str, interval: float = 0.01) -> dict:
    ensure_enabled()
    pyautogui.write(text, interval=interval)
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "type", "text": text}


def key_press(key: str) -> dict:
    ensure_enabled()
    if "+" in key:
        pyautogui.hotkey(*[k.strip() for k in key.split("+") if k.strip()])
    else:
        pyautogui.press(key.strip())
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "key", "key": key}


def key_sequence(keys: list[str], inter_key_delay_ms: int = 70) -> dict:
    ensure_enabled()
    if not keys:
        raise ValueError("keys cannot be empty")
    for key in keys:
        if "+" in key:
            pyautogui.hotkey(*[k.strip() for k in key.split("+") if k.strip()])
        else:
            pyautogui.press(key.strip())
        time.sleep(max(0, inter_key_delay_ms) / 1000)
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "key_sequence", "keys": keys, "inter_key_delay_ms": inter_key_delay_ms}


def garageband_shortcut(name: str) -> dict:
    ensure_enabled()
    shortcut = GARAGEBAND_SHORTCUTS.get(name.strip().lower())
    if not shortcut:
        raise ValueError(f"Unknown GarageBand shortcut: {name}")
    return key_press(shortcut)


def scroll(amount: int) -> dict:
    ensure_enabled()
    pyautogui.scroll(amount)
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "scroll", "amount": amount}


def drag(x: int, y: int, duration: float = 0.2) -> dict:
    ensure_enabled()
    pyautogui.dragTo(x, y, duration=duration)
    time.sleep(settings.post_action_delay_ms / 1000)
    return {"ok": True, "action": "drag", "x": x, "y": y, "duration": duration}
