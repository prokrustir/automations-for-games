"""Screenshots, template matching and clicking, with stop/timeout handling."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np
import pyautogui

pyautogui.FAILSAFE = True  # slam the mouse into a screen corner to abort
pyautogui.PAUSE = 0.1

Region = tuple[int, int, int, int]  # left, top, width, height (screen pixels)


class Aborted(Exception):
    """User pressed Stop (or pyautogui failsafe)."""


class NeedsHuman(Exception):
    """The script hit something it does not know how to handle."""

    def __init__(self, message: str, screenshot: Path | None = None):
        super().__init__(message)
        self.screenshot = screenshot


@dataclass
class Match:
    name: str
    x: int  # top-left, screen coords
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


class Vision:
    def __init__(
        self,
        template_dir: Path,
        debug_dir: Path,
        threshold: float,
        stop_event: threading.Event,
        log: Callable[[str], None],
        after_click: float = 2.0,
    ):
        self.template_dir = template_dir
        self.debug_dir = debug_dir
        self.threshold = threshold
        self.stop = stop_event
        self.log = log
        self.after_click = after_click
        self._cache: dict[str, np.ndarray] = {}
        debug_dir.mkdir(parents=True, exist_ok=True)

    # ---------- basics ----------
    def check_stop(self) -> None:
        if self.stop.is_set():
            raise Aborted()

    def sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_stop()
            time.sleep(min(0.2, end - time.monotonic()))

    def screenshot(self, region: Region | None = None) -> np.ndarray:
        img = pyautogui.screenshot(region=region)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def save_debug(self, img: np.ndarray | None = None, tag: str = "screen") -> Path:
        if img is None:
            img = self.screenshot()
        path = self.debug_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{tag}.png"
        cv2.imwrite(str(path), img)
        return path

    def has(self, name: str) -> bool:
        return (self.template_dir / f"{name}.png").exists()

    def template(self, name: str) -> np.ndarray:
        if name not in self._cache:
            path = self.template_dir / f"{name}.png"
            if not path.exists():
                raise NeedsHuman(f"Template missing: {path.name}. Capture it with capture_template.py.")
            self._cache[name] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        return self._cache[name]

    # ---------- matching ----------
    def _match(self, name: str, region: Region | None) -> tuple[np.ndarray, int, int]:
        tpl = self.template(name)
        hay = cv2.cvtColor(self.screenshot(region), cv2.COLOR_BGR2GRAY)
        if hay.shape[0] < tpl.shape[0] or hay.shape[1] < tpl.shape[1]:
            return np.zeros((1, 1), np.float32), 0, 0
        res = cv2.matchTemplate(hay, tpl, cv2.TM_CCOEFF_NORMED)
        ox, oy = (region[0], region[1]) if region else (0, 0)
        return res, ox, oy

    def find(self, name: str, region: Region | None = None, threshold: float | None = None) -> Match | None:
        res, ox, oy = self._match(name, region)
        _, best, _, loc = cv2.minMaxLoc(res)
        if best < (threshold or self.threshold):
            return None
        h, w = self.template(name).shape
        return Match(name, loc[0] + ox, loc[1] + oy, w, h, float(best))

    def find_all(self, name: str, region: Region | None = None, threshold: float | None = None) -> list[Match]:
        res, ox, oy = self._match(name, region)
        h, w = self.template(name).shape
        ys, xs = np.where(res >= (threshold or self.threshold))
        found: list[Match] = []
        for x, y in sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]]):
            if all(abs(x + ox - m.x) > w // 2 or abs(y + oy - m.y) > h // 2 for m in found):
                found.append(Match(name, int(x + ox), int(y + oy), w, h, float(res[y, x])))
        return found

    def best_score(self, name: str, region: Region | None = None) -> float:
        res, _, _ = self._match(name, region)
        return float(res.max())

    def wait_for(
        self,
        names: str | Iterable[str],
        timeout: float,
        region: Region | None = None,
        interval: float = 1.0,
    ) -> Match:
        names = [names] if isinstance(names, str) else list(names)
        end = time.monotonic() + timeout
        while True:
            self.check_stop()
            for n in names:
                m = self.find(n, region)
                if m:
                    return m
            if time.monotonic() > end:
                shot = self.save_debug(tag="timeout")
                raise NeedsHuman(f"Timed out after {timeout:.0f}s waiting for: {', '.join(names)}", shot)
            time.sleep(interval)

    # ---------- input ----------
    def click_at(self, x: int, y: int, double: bool = False) -> None:
        self.check_stop()
        if double:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.click(x, y)

    def click(
        self,
        target: str | Match,
        timeout: float = 30,
        offset: tuple[int, int] = (0, 0),
        region: Region | None = None,
        settle: float | None = None,
    ) -> Match:
        m = target if isinstance(target, Match) else self.wait_for(target, timeout, region)
        cx, cy = m.center
        self.click_at(cx + offset[0], cy + offset[1])
        self.log(f"  click {m.name} ({m.score:.2f})")
        self.sleep(self.after_click if settle is None else settle)
        return m
