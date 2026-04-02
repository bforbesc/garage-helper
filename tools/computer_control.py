from __future__ import annotations

import base64
import io
import time
from datetime import datetime
from pathlib import Path

import mss
import mss.tools
import pyautogui
from PIL import Image

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
    "select_track_above": "up",
    "select_track_below": "down",
    "go_to_beginning": "return",
    "record": "r",
    "delete_selected": "backspace",
    "select_all": "command+a",
    "join_regions": "command+j",
    "zoom_in": "command+right",
    "zoom_out": "command+left",
    "musical_typing": "command+shift+k",
    "create_new_project": "command+n",
    "export_song": "command+shift+e",
    "close_project": "command+w",
}


def ensure_enabled() -> None:
    if not settings.enable_computer_control:
        raise PermissionError("Computer control disabled. Set ENABLE_COMPUTER_CONTROL=true to allow UI actions.")


def _ensure_screenshots_dir() -> Path:
    path = Path(settings.screenshots_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _downscale_screenshot(path: Path, max_width: int) -> str:
    """Open image, resize if wider than *max_width*, return base64 PNG string."""
    img = Image.open(path)
    if img.width <= max_width:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    ratio = max_width / img.width
    new_size = (max_width, int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def screenshot() -> dict:
    out_dir = _ensure_screenshots_dir()
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    path = out_dir / filename
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    b64 = _downscale_screenshot(path, settings.screenshot_max_width)
    return {"path": str(path), "base64_png": b64}


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
