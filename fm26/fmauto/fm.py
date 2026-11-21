"""Football Manager 26 screen actions."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pyautogui

from . import ocr
from .vision import Match, NeedsHuman, Region, Vision
from .windows import AppWindow

MATCH_DAY = ["fm_review_team_selection", "fm_go_to_match"]


@dataclass
class Result:
    outcome: str  # win / draw / loss
    ours: int
    theirs: int
    home: bool
    card_text: str

    def short(self) -> str:
        where = "home" if self.home else "away"
        return f"{self.outcome.upper()} {self.ours}-{self.theirs} ({where})"


class FM:
    def __init__(self, cfg: dict, vision: Vision, log):
        self.cfg = cfg
        self.v = vision
        self.log = log
        self.t = cfg["timeouts"]
        self.off = cfg["offsets"]
        self.win = AppWindow(cfg["fm_exe"], "Football Manager 26", backend="win32")  # launched via cfg["fm_launch"]

    # ---------- window ----------
    def focus(self) -> None:
        self.win.focus()
        self.v.sleep(self.cfg["delays"]["after_focus"])

    def minimize(self) -> None:
        self.win.minimize()
        self.v.sleep(1)

    def region(self) -> Region:
        return self.win.rect()

    # ---------- match day ----------
    def at_match_day(self) -> bool:
        return any(self.v.find(n, self.region()) for n in MATCH_DAY)

    def go_on_holiday(self) -> None:
        self.log("Holiday until next match")
        self.v.click("fm_calendar", self.t["click"])
        self.v.click("fm_go_on_holiday", self.t["click"])
        self.v.click("fm_return_date_label", self.t["click"], offset=tuple(self.off["return_date_dropdown_from_label"]))
        self.v.click("fm_next_match_option", self.t["click"])
        self.v.click("fm_confirm_holiday", self.t["click"])
        self.v.wait_for(MATCH_DAY, self.t["holiday"])
        self.log("Match day reached")

    def save(self) -> None:
        self.log("Saving (Ctrl+S)")
        x, y, _, _ = self.region()
        fx, fy = self.off["save_focus_point_from_window_topleft"]
        self.v.click_at(x + fx, y + fy)  # give FM keyboard focus
        self.v.sleep(1)
        pyautogui.hotkey("ctrl", "s")
        self.v.sleep(self.cfg["delays"]["after_save_key"])
        self.v.wait_for(MATCH_DAY, self.t["save"])
        self.log("Saved")

    def play_instant_result(self) -> None:
        self.log("Instant Result")
        m = self.v.wait_for(MATCH_DAY + ["fm_instant_result"], self.t["click"])
        if m.name == "fm_review_team_selection":
            self.v.click(m)
        self.v.click("fm_instant_result", self.t["click"])
        clicked_continue = False
        while True:
            m = self.v.wait_for(
                ["fm_dialog_confirm", "fm_dialog_yes", "fm_dialog_ok", "fm_bn_header", "fm_continue"],
                self.t["simulate"],
            )
            if m.name == "fm_bn_header":
                return
            if m.name in ("fm_dialog_confirm", "fm_dialog_yes"):
                self.v.click(m)  # 'leave to staff?' / 'only N substitutes' / 'not fully fit'
                continue
            if m.name == "fm_dialog_ok":
                raise NeedsHuman(
                    "FM says a player is injured and unavailable (probably on the bench). Remove him and re-run.",
                    self.v.save_debug(tag="injured"),
                )
            if m.name == "fm_continue":
                if clicked_continue:
                    raise NeedsHuman("Match finished but no Breaking News screen.", self.v.save_debug(tag="no_result"))
                self.log("  no Breaking News, clicking Continue")
                self.v.click(m, settle=15)
                clicked_continue = True

    def read_result(self) -> Result:
        hdr = self.v.wait_for("fm_bn_header", 30)
        dx, dy, w, h = self.off["card_region_from_bn_header"]
        cx, cy = hdr.center
        card: Region = (cx + dx, cy + dy, w, h)
        card_img = self.v.screenshot(card)
        crest = self._topmost(self.v.find_all("fm_our_crest", card))
        if not crest:
            raise NeedsHuman("Could not find our crest on the result card.", self.v.save_debug(card_img, "card"))
        half = self.off["score_search_halfwidth"]
        ccx, ccy = crest.center
        strip: Region = (ccx - half, crest.y - 5, 2 * half, crest.h + 10)
        score = ocr.read_score(self.v.screenshot(strip), half)
        if not score:
            raise NeedsHuman("Could not OCR the score.", self.v.save_debug(self.v.screenshot(strip), "score"))
        text = ocr.read_text(card_img)
        outcome = ocr.classify(score, text, self.cfg["result_loss_words"])
        return Result(outcome, score.ours, score.theirs, score.home, text.strip())

    def reload_last_save(self) -> None:
        self.log("Reloading the pre-match save")
        self.v.click("fm_latest_results", self.t["click"], settle=10)
        self.v.click("fm_settings", self.t["click"], settle=5)
        self.v.click("fm_load_game", self.t["click"], settle=8)
        self.v.click("fm_dialog_no", self.t["click"], settle=8)  # never save the lost match
        self._load_newest_save()
        self.v.wait_for(MATCH_DAY, self.t["load_game"])
        self.log("Save loaded")

    def _load_newest_save(self) -> None:
        """In the Load Game list: pick the newest 'Kolo Kolo - Wieczysta Kraków' row and press Load."""
        self.v.wait_for("fm_save_row", self.t["click"])
        rows = self.v.find_all("fm_save_row", self.region())
        if not rows:
            raise NeedsHuman("Save list: no 'Wieczysta' save row found.", self.v.save_debug(tag="saves"))
        self.v.click(self._topmost(rows), settle=4)  # list is sorted newest first
        self.v.click("fm_load_btn", self.t["click"])

    # ---------- session start ----------
    def ensure_game_loaded(self) -> bool:
        """Start FM if needed and load the newest Wieczysta save.

        Returns True if a save was loaded now (FMRTE must then re-attach), False if FM was already in a game.
        """
        if not self.win.is_running():
            self.log("Starting FM26 via Steam")
            self.win.launch(self.cfg["fm_launch"])
            self.win.wait_running(self.t["fm_start"], self.v)
        self.focus()
        needed = ("fm_settings", "fm_start_most_recent")
        missing = [n for n in needed if not self.v.has(n)]
        if missing:
            raise NeedsHuman(
                f"Missing templates: {', '.join(missing)}. Capture them with capture_template.py "
                "(fm_settings in game, fm_start_most_recent on the start screen)."
            )
        options = [n for n in ("fm_settings", "fm_start_most_recent", "fm_start_load_game") if self.v.has(n)]
        self.log("  waiting for FM start screen or in-game screen")
        m = self.v.wait_for(options, self.t["fm_start"])
        if m.name == "fm_settings":
            self.log("FM is already in a game, not loading")
            return False
        if m.name == "fm_start_most_recent":
            # 'Load Most Recent Career' tile: loads the last played save directly
            self.log("FM start screen: Load Most Recent Career")
            self.v.click(m, offset=tuple(self.off["most_recent_click_from_title"]), settle=8)
        else:
            self.log("FM start screen: Load Game")
            self.v.click(m, settle=8)
            self._load_newest_save()
        self.v.wait_for("fm_settings", self.t["load_game"])
        self.v.sleep(5)
        self.log("Save loaded")
        return True

    # ---------- inbox ----------
    def open_unread(self) -> Match:
        if self.v.find("fm_bn_header"):
            self.v.click("fm_latest_results", self.t["click"], settle=10)
        self.v.click("fm_messages_tab", self.t["click"], settle=8)
        return self.v.click("fm_unread_filter", self.t["click"], settle=5)

    def unread_count(self, unread: Match) -> int | None:
        txt = ocr.read_text(self.v.screenshot((unread.x, unread.y, unread.w + 20, unread.h)))
        m = re.search(r"\((\d+)\)", txt)
        return int(m.group(1)) if m else None

    def read_message_list(self, unread: Match, max_pages: int = 20) -> list[str]:
        cx, cy = unread.center
        dx, dy, w, h = self.off["message_list_from_unread_filter"]
        sx, sy = self.off["message_list_scroll_point_from_unread_filter"]
        region: Region = (cx + dx, cy + dy, w, h)
        pages, last = [], None
        for _ in range(max_pages):
            txt = ocr.read_text(self.v.screenshot(region))
            if txt == last:
                break
            pages.append(txt)
            last = txt
            pyautogui.moveTo(cx + sx, cy + sy)
            pyautogui.scroll(-5)
            self.v.sleep(2)
        lines: list[str] = []
        for p in pages:
            for line in p.splitlines():
                line = line.strip()
                if line and line not in lines:
                    lines.append(line)
        return lines

    def mark_all_read(self) -> None:
        self.v.click("fm_mark_all_read", self.t["click"], settle=5)

    # ---------- utils ----------
    @staticmethod
    def _topmost(matches: list[Match]) -> Match | None:
        return min(matches, key=lambda m: m.y) if matches else None
