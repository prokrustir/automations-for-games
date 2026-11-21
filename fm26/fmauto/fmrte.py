"""FMRTE: start without elevation, load FM's memory, open the first team, Heal.

Window handling uses the win32 backend (never hangs). Buttons are found by image
templates first; Windows UI Automation (by button title) is only a fallback and runs
with a hard timeout, because UIA queries can hang on FMRTE. After the first UIA timeout
UIA is switched off for the rest of the session.
Only ever clicks the exact 'Heal' control. 'Destroy' sits two rows below it.
"""

from __future__ import annotations

import threading

from pywinauto import Application

from .vision import NeedsHuman, Vision
from .windows import AppWindow

UIA_TIMEOUT = 8  # seconds


def _with_timeout(fn, seconds: float):
    box: dict = {}

    def run():
        try:
            box["v"] = fn()
        except Exception as e:  # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError
    if "e" in box:
        raise box["e"]
    return box.get("v")


class FMRTE:
    def __init__(self, cfg: dict, vision: Vision, log):
        self.cfg = cfg
        self.v = vision
        self.log = log
        self.win = AppWindow(cfg["fmrte_exe"], "FMRTE", backend="win32")
        self.uia_ok = bool(cfg.get("fmrte_use_uia", True))

    # ---------- UIA fallback (time-limited) ----------
    def _uia(self, what: str, fn) -> object | None:
        if not self.uia_ok:
            return None
        pid = self.win.pid()
        if pid is None:
            return None

        def call():
            w = Application(backend="uia").connect(process=pid, timeout=3).top_window()
            return fn(w)

        try:
            return _with_timeout(call, UIA_TIMEOUT)
        except TimeoutError:
            self.uia_ok = False
            self.log(f"  UI Automation not responding ({what}); using image templates only from now on")
        except Exception as e:  # noqa: BLE001
            self.log(f"  UIA '{what}' failed: {e}")
        return None

    def _uia_exists(self, **spec) -> bool:
        return bool(self._uia(f"exists {spec}", lambda w: w.child_window(**spec).exists(timeout=1)))

    def _uia_click(self, title: str) -> bool:
        def click(w):
            c = w.child_window(title=title)
            if c.exists(timeout=1):
                c.click_input()
                return True
            return False

        ok = bool(self._uia(f"click {title}", click))
        if ok:
            self.log(f"  FMRTE click '{title}' (UIA)")
            self.v.sleep(1.5)
        return ok

    # ---------- template-first helpers ----------
    def _click(self, title: str, template: str, timeout: float = 5) -> None:
        if self.v.has(template):
            m = self.v.find(template)
            if m:
                self.v.click(m)
                return
        if self._uia_click(title):
            return
        if self.v.has(template):
            self.v.click(template, timeout=timeout)  # wait a bit longer for it
            return
        raise NeedsHuman(
            f"FMRTE: can't find '{title}'. Capture the {template} template.",
            self.v.save_debug(tag="fmrte"),
        )

    def _reload_prompt_visible(self) -> bool:
        if self.v.has("fmrte_reload_prompt"):
            return self.v.find("fmrte_reload_prompt") is not None
        return self._uia_exists(title_re=".*(reload your save|loaded another savegame).*")

    def _heal_visible(self) -> bool:
        if self.v.has("fmrte_heal"):
            return self.v.find("fmrte_heal") is not None
        return self._uia_exists(title="Heal")

    def _focus(self) -> None:
        self.win.focus()
        self.v.sleep(1.5)

    # ---------- public ----------
    def reattach_if_needed(self) -> None:
        """After FM loads a save, FMRTE asks to reload. Click Ok, then Load Game."""
        self._focus()
        if not self._reload_prompt_visible():
            return
        self.log("FMRTE asks to reload the save, reattaching")
        self._click("Ok", "fmrte_ok")
        self._load_game()

    def _load_game(self) -> None:
        self.log("FMRTE: Load Game (reading FM memory)")
        self._click("Load Game", "fmrte_load_game", timeout=15)
        timeout = self.cfg["timeouts"]["fmrte_reload"]
        if self.v.has("fmrte_game_loaded"):
            # status bar text 'Game was loaded' appears when FMRTE has read FM's memory
            self.v.wait_for("fmrte_game_loaded", timeout, interval=1.0)
            self.log("FMRTE: game loaded")
            self.v.sleep(2)
        else:
            self.v.sleep(timeout)
        if self._reload_prompt_visible():
            raise NeedsHuman("FMRTE still asks to reload the save after Load Game.", self.v.save_debug(tag="fmrte"))

    def ensure_attached(self, force_load: bool) -> None:
        """Start FMRTE if needed and load FM's memory ('Load Game'), then open the first-team squad.

        force_load: FM has just loaded a save (or was restarted), so FMRTE must re-read memory
        even if it does not show the 'reload your save' prompt.
        """
        started = False
        if self.win.is_running() and self.win.is_elevated():
            raise NeedsHuman(
                "FMRTE is running as administrator, so it can't be clicked. Close it; "
                "Start session will reopen it without elevation."
            )
        if not self.win.is_running():
            self.log("Starting FMRTE (without elevation)")
            self.win.launch(self.cfg["fmrte_exe"], run_as_invoker=self.cfg.get("fmrte_run_as_invoker", True))
            self.win.wait_running(self.cfg["timeouts"]["fmrte_start"], self.v)
            self.v.sleep(8)  # let FMRTE finish its start-up screen
            started = True
        self._focus()
        if self._reload_prompt_visible():
            self._click("Ok", "fmrte_ok")
            force_load = True
        if started or force_load:
            self._load_game()
        self.open_first_team()
        self.log("FMRTE attached, first-team squad open")

    def open_first_team(self) -> None:
        """Show Wieczysta Kraków > Squads > first team, using optional templates."""

        def shown() -> bool:
            if not self._heal_visible():
                return False
            return not self.v.has("fmrte_first_team_marker") or self.v.find("fmrte_first_team_marker") is not None

        def click_if_visible(name: str) -> None:
            if self.v.has(name):
                m = self.v.find(name)
                if m:
                    self.v.click(m, settle=2)

        self._focus()  # anything else (e.g. the Claude window) may have taken the front
        if not shown():
            # club tab already open but not selected
            click_if_visible("fmrte_club_tab")
            # fresh FMRTE: Favorites > Kolo Kolo > Wieczysta Kraków opens the club
            if not self._heal_visible() and all(
                self.v.has(n) for n in ("fmrte_favorites", "fmrte_fav_manager", "fmrte_fav_club")
            ):
                self.log("FMRTE: opening club via Favorites")
                self.v.click("fmrte_favorites", timeout=5, settle=1.5)
                self.v.click("fmrte_fav_manager", timeout=5, settle=1.5)
                self.v.click("fmrte_fav_club", timeout=5, settle=4)
            if not self._heal_visible():
                click_if_visible("fmrte_squads_menu")
                self.v.sleep(2)
        click_if_visible("fmrte_first_team_tab")  # FMRTE may remember the U19 / Youth sub-tab
        if not shown():
            raise NeedsHuman(
                "FMRTE: couldn't reach Wieczysta Kraków > Squads (first team). "
                "If the club page opened but not Squads, capture fmrte_squads_menu.",
                self.v.save_debug(tag="fmrte"),
            )

    def heal(self) -> None:
        self.log("Heal in FMRTE")
        self.reattach_if_needed()
        self._focus()
        self.open_first_team()  # FMRTE remembers the last sub-tab, e.g. Youth Candidates
        self._click("Heal", "fmrte_heal")
        self.log("Heal done (FMRTE shows no confirmation)")
