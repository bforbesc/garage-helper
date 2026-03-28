from __future__ import annotations

import base64
import time
from datetime import datetime
from pathlib import Path

import mss
import mss.tools
import pyautogui

from config import settings

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


def ensure_enabled() -> None:
    if not settings.enable_computer_control:
        raise PermissionError("Computer control disabled. Set ENABLE_COMPUTER_CONTROL=true to allow UI actions.")


def _ensure_screenshots_dir() -> Path:
    path = Path(settings.screenshots_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshot() -> dict:
    ensure_enabled()
    out_dir = _ensure_screenshots_dir()
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    path = out_dir / filename
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
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
