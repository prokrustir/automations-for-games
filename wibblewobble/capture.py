"""Save screenshots of the emulator for building templates.

Usage:
    python capture.py              # one screenshot
    python capture.py battle_start # one screenshot, name prefix "battle_start"
    python capture.py --loop       # press Enter for each shot, type q to quit

Screenshots are saved exactly as Maa sees the screen (scaled to 720p),
so templates cut from them match 1:1. Also prints the foreground app package.
"""
import subprocess
import sys
import time
from pathlib import Path

import cv2

from common import ROOT, connect, load_config


def foreground_app(adb_path: str, address: str) -> str:
    try:
        out = subprocess.run(
            [adb_path, "-s", address, "shell", "dumpsys", "window"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                return line.strip()
    except Exception as e:  # noqa: BLE001
        return f"(could not read: {e})"
    return "(unknown)"


def shoot(controller, out_dir: Path, prefix: str) -> Path:
    img = controller.post_screencap().wait().get()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.png"
    cv2.imwrite(str(path), img)  # Maa returns BGR numpy array -> lossless PNG
    h, w = img.shape[:2]
    print(f"Saved {path.name}  ({w}x{h})")
    return path


def main():
    cfg = load_config()
    controller = connect(cfg)
    out_dir = ROOT / cfg.get("screenshots_dir", "screenshots")

    args = [a for a in sys.argv[1:] if a != "--loop"]
    prefix = args[0] if args else "shot"

    cfg_adb = cfg.get("adb_path")
    # Foreground app helps us fill in the game's package name for StartApp.
    from maa.toolkit import Toolkit
    dev = next(iter(Toolkit.find_adb_devices()), None)
    if dev:
        print("Foreground:", foreground_app(cfg_adb or dev.adb_path, cfg.get("adb_address") or dev.address))

    if "--loop" in sys.argv:
        while True:
            name = input("Name for this screen (Enter = keep last, q = quit): ").strip()
            if name.lower() == "q":
                break
            prefix = name or prefix
            shoot(controller, out_dir, prefix)
    else:
        shoot(controller, out_dir, prefix)


if __name__ == "__main__":
    main()
