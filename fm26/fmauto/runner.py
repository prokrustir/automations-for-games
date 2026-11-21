"""High-level flows used by the launcher buttons."""

from __future__ import annotations

from . import triage as triage_mod
from .fm import FM, Result
from .fmrte import FMRTE
from .vision import NeedsHuman


def start_session(fm: FM, fmrte: FMRTE, cfg: dict, log) -> None:
    """Start FM (Steam) and load the newest Wieczysta save, then start FMRTE and load FM's memory."""
    log("=== Start session ===")
    loaded_now = fm.ensure_game_loaded()
    fm.minimize()  # FMRTE sits behind the FM window
    fmrte.ensure_attached(force_load=loaded_now)
    fm.focus()
    log("Session ready")


def inbox(fm: FM, cfg: dict, log) -> bool:
    """Returns True if the inbox is clear (marked read or already empty), False if something needs you."""
    log("=== Inbox triage ===")
    fm.focus()
    unread = fm.open_unread()
    count = fm.unread_count(unread)
    log(f"Unread: {count if count is not None else '?'}")
    if count == 0:
        return True
    lines = fm.read_message_list(unread)
    t = triage_mod.classify(lines, cfg["triage"])
    if t.safe_to_mark_read:
        fm.mark_all_read()
        log(f"Nothing important ({t.skipped} lines). Marked all as read.")
        return True
    log("IMPORTANT messages, left unread:")
    for line in t.important:
        log(f"  ! {line}")
    return False


def match_day(fm: FM, fmrte: FMRTE, cfg: dict, log) -> Result:
    log("=== Match day ===")
    fm.focus()
    if not fm.at_match_day():
        fm.go_on_holiday()

    if cfg.get("heal_before_match", True):
        try:
            fm.minimize()
            fmrte.heal()
        except NeedsHuman as e:
            log(f"Heal skipped: {e}")
        fm.focus()

    fm.save()

    attempts = int(cfg.get("max_retries_on_loss", 10))
    history: list[str] = []
    result: Result | None = None
    for attempt in range(1, attempts + 1):
        fm.play_instant_result()
        result = fm.read_result()
        history.append(result.short())
        log(f"Attempt {attempt}: {result.short()}")
        if result.outcome != "loss":
            break
        if attempt == attempts:
            log(f"Lost {attempts} times in a row, keeping the last result.")
            break
        fm.reload_last_save()
        try:
            fm.minimize()
            fmrte.reattach_if_needed()  # FMRTE needs 'Load Game' after every FM reload
        except NeedsHuman as e:
            log(f"FMRTE reattach failed: {e}")
        fm.focus()

    assert result is not None
    log(f"Final: {result.short()}  | history: {' / '.join(history)}")
    first_line = result.card_text.splitlines()[0] if result.card_text else ""
    if first_line:
        log(f"Headline: {first_line}")
    return result
