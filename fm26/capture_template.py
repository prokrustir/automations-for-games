"""Capture a template image for the script.

Usage:
  python capture_template.py --list            # show all templates and which are missing
  python capture_template.py fm_instant_result # 3 s countdown, screenshot, drag a box, Enter to save

Tips: crop tightly around stable text/icons; leave out numbers or dates that change.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import fmauto  # noqa: F401  (DPI awareness)
import cv2
import numpy as np
import pyautogui

from fmauto.catalog import OPTIONAL, TEMPLATES

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--delay", type=float, default=3.0)
    a = ap.parse_args()
    TPL.mkdir(exist_ok=True)

    if a.list or not a.name:
        for n, desc in TEMPLATES.items():
            have = "ok     " if (TPL / f"{n}.png").exists() else ("opt    " if n in OPTIONAL else "MISSING")
            print(f"{have} {n:28s} {desc}")
        return

    if a.name not in TEMPLATES:
        print(f"Unknown template '{a.name}'. Use --list.")
        return
    print(f"{a.name}: {TEMPLATES[a.name]}")
    for i in range(int(a.delay), 0, -1):
        print(f"  screenshot in {i}…  (switch to the game now)")
        time.sleep(1)
    img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
    win = f"Drag a box around: {a.name}  (Enter = save, c = cancel)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    x, y, w, h = cv2.selectROI(win, img, showCrosshair=False)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        print("Cancelled.")
        return
    out = TPL / f"{a.name}.png"
    cv2.imwrite(str(out), img[y : y + h, x : x + w])
    print(f"Saved {out} ({w}x{h})")


if __name__ == "__main__":
    main()
