"""FM26 automation: match-day loop and inbox triage driven by template matching + OCR."""

import ctypes
import sys

# Use physical pixels for screenshots and clicks, regardless of Windows display scaling.
# Must run before pyautogui / pywinauto are imported.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # older Windows
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
