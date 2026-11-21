"""Start, find and focus FM / FMRTE windows and read their geometry.

Process detection uses psutil (fast, never blocks). Window handling uses pywinauto:
backend 'win32' for FM (UI Automation queries can hang on a DirectX game window),
'uia' for FMRTE (so its buttons can be found by name).
"""

from __future__ import annotations

import os
import subprocess
import time

import psutil
from pywinauto import Application, findwindows

from .vision import NeedsHuman, Region, Vision


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class AppWindow:
    def __init__(self, exe: str, label: str, backend: str = "uia"):
        self.exe = exe
        self.label = label
        self.backend = backend
        self._app: Application | None = None
        self._pid: int | None = None

    def pid(self) -> int | None:
        target = _norm(self.exe)
        for p in psutil.process_iter(["exe"]):
            try:
                exe = p.info.get("exe")
                if exe and _norm(exe) == target:
                    return p.pid
            except (psutil.Error, OSError):
                continue
        return None

    def is_running(self) -> bool:
        return self.pid() is not None

    @property
    def app(self) -> Application:
        pid = self.pid()
        if pid is None:
            self._app = None
            raise NeedsHuman(f"{self.label} is not running. Start it (or use Start session) and try again.")
        if self._app is None or pid != self._pid:
            self._app = Application(backend=self.backend).connect(process=pid, timeout=10)
            self._pid = pid
        return self._app

    @property
    def window(self):
        """The process's main window: its largest visible top-level window.

        Not top_window(): that can return a short-lived popup (e.g. FMRTE's loading
        dialog) whose handle is gone a moment later (WinError 1400).
        """
        app = self.app
        best, best_area = None, -1
        for h in findwindows.find_windows(process=self._pid, visible_only=True):
            try:
                w = app.window(handle=h).wrapper_object()
                r = w.rectangle()
                area = r.width() * r.height()
                if area > best_area:
                    best, best_area = w, area
            except Exception:  # noqa: BLE001  (window closed meanwhile)
                continue
        return best if best is not None else app.top_window()

    def launch(self, command: str, run_as_invoker: bool = False) -> None:
        """Start the program: a steam:// URL or an .exe path.

        run_as_invoker: start an exe whose manifest asks for admin rights *without* elevation
        (Windows compatibility layer RunAsInvoker). No UAC prompt, and the window stays
        clickable for non-elevated programs (this script, Claude).
        """
        self._app = None
        if command.lower().startswith("steam://"):
            os.startfile(command)  # type: ignore[attr-defined]  (Windows only)
            return
        folder = os.path.dirname(command) or "."
        if run_as_invoker:
            # same as fmrte_bez_admina.bat: set the compat layer, then 'start' through cmd
            env = os.environ.copy()
            env["__COMPAT_LAYER"] = "RunAsInvoker"
            subprocess.Popen(f'start "" /D "{folder}" "{command}"', shell=True, env=env)
        else:
            subprocess.Popen([command], cwd=folder)

    def is_elevated(self) -> bool | None:
        """True if the running process has admin rights (then it can't be clicked from here)."""
        pid = self.pid()
        if pid is None:
            return None
        try:
            import ctypes
            from ctypes import wintypes

            k32, adv = ctypes.windll.kernel32, ctypes.windll.advapi32
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return None
            tok = wintypes.HANDLE()
            if not adv.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):  # TOKEN_QUERY
                k32.CloseHandle(h)
                return None
            elev, size = wintypes.DWORD(), wintypes.DWORD()
            ok = adv.GetTokenInformation(tok, 20, ctypes.byref(elev), 4, ctypes.byref(size))  # TokenElevation
            k32.CloseHandle(tok)
            k32.CloseHandle(h)
            return bool(elev.value) if ok else None
        except Exception:  # noqa: BLE001
            return None

    def wait_running(self, timeout: float, v: Vision) -> None:
        """Wait until the process exists and has a visible top-level window."""
        start = time.monotonic()
        last_log = 0.0
        while True:
            v.check_stop()
            pid = self.pid()
            if pid is not None:
                # plain EnumWindows: fast and never hangs (unlike UI Automation)
                if findwindows.find_windows(process=pid, visible_only=True):
                    v.log(f"  {self.label} window is up")
                    self._app = None
                    return
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise NeedsHuman(f"{self.label} did not start within {timeout:.0f}s.", v.save_debug(tag="start"))
            if elapsed - last_log >= 15:
                v.log(f"  waiting for {self.label}… {elapsed:.0f}s")
                last_log = elapsed
            v.sleep(3)

    def focus(self):
        last: Exception | None = None
        for _ in range(3):  # windows can appear/disappear while loading
            try:
                w = self.window
                if w.is_minimized():
                    w.restore()
                w.set_focus()
                return w
            except OSError as e:  # e.g. WinError 1400 invalid window handle
                last = e
                self._app = None
                time.sleep(1.5)
        raise NeedsHuman(f"Can't bring {self.label} to the front: {last}")

    def minimize(self) -> None:
        self.window.minimize()

    def rect(self) -> Region:
        r = self.window.rectangle()
        return r.left, r.top, r.width(), r.height()
