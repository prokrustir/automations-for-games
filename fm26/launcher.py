"""FM Auto launcher: a small window with buttons, so it can be driven by mouse (by you or by Claude).

Run:  python launcher.py
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

import fmauto  # noqa: F401  (sets DPI awareness first)
import pyautogui
from fmauto import ocr, runner
from fmauto.catalog import OPTIONAL, TEMPLATES
from fmauto.fm import FM
from fmauto.fmrte import FMRTE
from fmauto.vision import Aborted, NeedsHuman, Vision

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

(ROOT / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    filename=ROOT / "logs" / "fm_auto.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    encoding="utf-8",
)


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FM Auto")
        self.geometry("660x520")
        self.attributes("-topmost", False)
        self.stop_event = threading.Event()
        self.msgs: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None

        ocr.configure(CFG.get("tesseract_cmd", ""))
        self.vision = Vision(
            ROOT / "templates", ROOT / "debug", CFG["match_threshold"], self.stop_event, self.log,
            CFG["delays"]["after_click"],
        )
        self.fm = FM(CFG, self.vision, self.log)
        self.fmrte = FMRTE(CFG, self.vision, self.log)

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        self.buttons = [
            ttk.Button(bar, text="Start session", command=lambda: self.run(self.do_start)),
            ttk.Button(bar, text="Inbox triage", command=lambda: self.run(self.do_inbox)),
            ttk.Button(bar, text="Match day", command=lambda: self.run(self.do_match)),
            ttk.Button(bar, text="Inbox + Match ×N", command=lambda: self.run(self.do_loop)),
            ttk.Button(bar, text="Test templates", command=lambda: self.run(self.do_test)),
        ]
        for b in self.buttons:
            b.pack(side="left", padx=2)
        self.rounds = tk.IntVar(value=1)
        ttk.Spinbox(bar, from_=1, to=50, width=4, textvariable=self.rounds).pack(side="left", padx=4)
        ttk.Button(bar, text="STOP", command=self.stop_event.set).pack(side="right")

        self.status = tk.Label(self, text="Idle", anchor="w", font=("Segoe UI", 11, "bold"), fg="gray30")
        self.status.pack(fill="x", padx=8)
        self.text = scrolledtext.ScrolledText(self, height=24, font=("Consolas", 9))
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        self.after(150, self.pump)

    # ---------- logging ----------
    def log(self, msg: str) -> None:
        logging.info(msg)
        self.msgs.put(("log", f"{time.strftime('%H:%M:%S')} {msg}"))

    def set_status(self, text: str, color: str) -> None:
        self.msgs.put(("status", f"{color}|{text}"))

    def pump(self) -> None:
        while not self.msgs.empty():
            kind, payload = self.msgs.get()
            if kind == "log":
                self.text.insert("end", payload + "\n")
                self.text.see("end")
            else:
                color, text = payload.split("|", 1)
                self.status.config(text=text, fg=color)
        busy = self.worker is not None and self.worker.is_alive()
        for b in self.buttons:
            b.state(["disabled"] if busy else ["!disabled"])
        self.after(150, self.pump)

    # ---------- running ----------
    def run(self, fn) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        self.set_status("Running…", "dark blue")

        def wrapper():
            try:
                fn()
                self.set_status("Done", "dark green")
            except (Aborted, pyautogui.FailSafeException):
                self.log("Stopped by user")
                self.set_status("Stopped", "gray30")
            except NeedsHuman as e:
                shot = f" (screenshot: {e.screenshot.name})" if e.screenshot else ""
                self.log(f"NEEDS HUMAN: {e}{shot}")
                self.set_status(f"NEEDS HUMAN: {e}", "red")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {type(e).__name__}: {e}")
                logging.exception("unhandled")
                self.set_status(f"ERROR: {e}", "red")

        self.worker = threading.Thread(target=wrapper, daemon=True)
        self.worker.start()

    def do_start(self) -> None:
        runner.start_session(self.fm, self.fmrte, CFG, self.log)

    def do_inbox(self) -> None:
        if not runner.inbox(self.fm, CFG, self.log):
            raise NeedsHuman("Inbox has important messages, see log.")

    def do_match(self) -> None:
        runner.match_day(self.fm, self.fmrte, CFG, self.log)

    def do_loop(self) -> None:
        n = max(1, int(self.rounds.get()))
        for i in range(1, n + 1):
            self.log(f"##### Round {i}/{n}")
            if not runner.inbox(self.fm, CFG, self.log):
                raise NeedsHuman("Inbox has important messages, see log.")
            runner.match_day(self.fm, self.fmrte, CFG, self.log)
            self.fm.focus()

    def do_test(self) -> None:
        """Score every template against the current screen; helps calibration."""
        self.log("Template scores on the current screen (≥ threshold means found):")
        shot = self.vision.save_debug(tag="test_full")
        for name in TEMPLATES:
            path = ROOT / "templates" / f"{name}.png"
            if not path.exists():
                self.log(f"  {name:28s} MISSING{' (optional)' if name in OPTIONAL else ''}")
                continue
            score = self.vision.best_score(name)
            mark = "FOUND" if score >= CFG["match_threshold"] else ""
            self.log(f"  {name:28s} {score:.2f} {mark}")
        # debug crops for the offset-based regions, when their anchors are visible
        hdr = self.vision.find("fm_bn_header") if (ROOT / "templates/fm_bn_header.png").exists() else None
        if hdr:
            dx, dy, w, h = CFG["offsets"]["card_region_from_bn_header"]
            cx, cy = hdr.center
            self.log(f"  card crop -> {self.vision.save_debug(self.vision.screenshot((cx+dx, cy+dy, w, h)), 'card').name}")
        un = self.vision.find("fm_unread_filter") if (ROOT / "templates/fm_unread_filter.png").exists() else None
        if un:
            dx, dy, w, h = CFG["offsets"]["message_list_from_unread_filter"]
            cx, cy = un.center
            self.log(f"  message list crop -> {self.vision.save_debug(self.vision.screenshot((cx+dx, cy+dy, w, h)), 'msglist').name}")
        self.log(f"Full screenshot: {shot.name}")


if __name__ == "__main__":
    Launcher().mainloop()
