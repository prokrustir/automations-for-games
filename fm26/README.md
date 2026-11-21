# FM Auto (FM26 + FMRTE)

Scripted version of the `fm-inbox-triage` and `fm-match-day` skills. A small launcher window has buttons; the script does the clicking and stops with **NEEDS HUMAN** when it sees something it doesn't know. The launcher is a normal desktop window, so Claude can also press its buttons via computer use.

## What it does

| Button | Flow |
|---|---|
| **Start session** | If FM isn't running: starts it through Steam (`fm_launch`), waits for the start screen and clicks the **Load Most Recent Career** tile (fallback: **Load Game** → newest "Kolo Kolo - Wieczysta Kraków" save), then waits until in game. If FMRTE isn't running: starts it. Then FMRTE **Load Game** (reads FM's memory; also done if FMRTE was already open, since the save just changed) and opens Wieczysta Kraków → Squads → first team. If FM was already in a game, nothing is reloaded. |
| **Inbox triage** | Messages → Unread → OCR the list → if nothing matches the `important` keywords, **Mark all as read**; otherwise list the hits and stop. |
| **Match day** | Holiday until next match (skipped if already match day) → FMRTE Heal (reattaches after a reload) → Ctrl+S → Instant Result (confirms the usual dialogs) → OCR the score. On a **loss** (or a draw whose headline reads like a defeat, e.g. a penalty exit) it reloads the pre-match save and replays, up to `max_retries_on_loss` (10). |
| **Inbox + Match ×N** | Repeats both, N times (spinbox). |
| **Test templates** | Scores every template against the current screen and saves debug crops in `debug/`. Use it for calibration. |
| **STOP** | Stops after the current step. Moving the mouse into a screen corner also aborts (pyautogui failsafe). |

Logs: `logs/fm_auto.log`. Screenshots of every NEEDS HUMAN stop: `debug/`.

## Setup (once)

1. **Python 3.10+** (64-bit). Then in this folder:
   ```
   pip install -r requirements.txt
   ```
2. **Tesseract OCR** for Windows (UB Mannheim build). Install it and check `tesseract_cmd` in `config.json`.
3. Check `fm_exe` and `fmrte_exe` paths in `config.json`.
4. **Fix FM's window size and position.** Templates match only at the pixel size they were captured. Keep FM windowed at one size (or always fullscreen), and keep Windows display scaling unchanged.
5. **Capture the templates.** List them with:
   ```
   python capture_template.py --list
   ```
   Then for each one: open the right FM screen, run `python capture_template.py <name>`, switch to FM during the 3 s countdown, drag a tight box, press Enter. Crop stable text or icons only; leave out dates and numbers (e.g. capture `Next match`, not `Next match (5/5/29)`).
6. **Calibrate offsets.** Open the relevant screen and press **Test templates**:
   - holiday dialog open → check that clicking at `return_date_dropdown_from_label` hits the dropdown (adjust the x offset);
   - a Breaking News screen → the saved `*_card.png` must contain the big result card with both crests and the score;
   - Messages with Unread selected → `*_msglist.png` must contain the message list.

   Adjust `offsets` in `config.json` until the crops are right. All values are in native screen pixels.

## Running

```
python launcher.py
```

Before you start:
- Close **Task Manager** (or any app running as administrator). Windows blocks input from normal programs to elevated windows, so the script's clicks would be ignored.
- FM and FMRTE must both be running, with FMRTE attached to the save.
- Leave the mouse alone while it runs.

## How it decides

- **Important messages:** a line containing any `triage.important` keyword, unless it also contains a `triage.important_exceptions` phrase. OCR sees sender + first line (or the title in a wide window), so rules are plain substrings. Unlike the agent, the script can't spot new types of message; it only knows these keywords. Add to the lists as you go.
- **Result:** the score is read next to the Wieczysta crest on the big card. The crest's side (left/right of the score) gives home/away. A draw counts as a loss only if the card text contains a `result_loss_words` entry (penalty exits read like "suffer … disappointment").
- **Injured player on the bench** ("is injured, and is unavailable"): stops with NEEDS HUMAN. Remove him from the bench, then press Match day again.
- **No Breaking News after the match:** clicks Continue once, then expects the result screen.

## Start session notes

- FM is started with `steam://rungameid/3551340`, so Steam must be running (or able to start) and logged in.
- "In game" is recognised by the gear icon (`fm_settings`). If FM's start screen also shows that icon, recapture `fm_settings` from inside the game only.
- "Load Most Recent Career" loads whatever you played last. Check the tile shows Wieczysta Kraków if you also play other careers.
- In the Load Game fallback the save list is sorted newest first; the script takes the top Wieczysta row. Make sure no other save of that career (e.g. a manual "v02" copy) is newer than the one you want.
- FMRTE must run **without** administrator rights; otherwise Windows shows a UAC prompt the script can't click, and its buttons can't be clicked either.
- A freshly started FMRTE doesn't show your club. Either capture `fmrte_open_club` (+ `fmrte_squads_menu`) so the script can open it, or open Wieczysta Kraków → Squads by hand once. The script stops with NEEDS HUMAN and says so.

## Known limits / first-run checklist

- Template matching is single-scale. If FM's size changes, recapture.
- FMRTE is driven via Windows UI Automation by button title (`Heal`, `Ok`, `Load Game`), with image templates as fallback. If UIA doesn't see FMRTE's buttons, capture the `fmrte_*` templates.
- The Steam "account signed in elsewhere" toast can cover FM's Load button; `fm_load_btn` should be the left part of the button only.
- First runs: watch it. Press STOP if anything looks off, and send the log plus the debug screenshot to Claude.

## Files

```
launcher.py           GUI with buttons (entry point)
capture_template.py   template capture helper (--list shows what's missing)
config.json           paths, timeouts, offsets, keyword rules
fmauto/vision.py      screenshot, template matching, clicking, Stop/timeout
fmauto/windows.py     focus / minimize FM and FMRTE (pywinauto)
fmauto/fm.py          FM screens: holiday, save, instant result, read result, reload, inbox
fmauto/fmrte.py       FMRTE: reattach after reload, Heal
fmauto/ocr.py         Tesseract helpers: score, text
fmauto/triage.py      keyword rules
fmauto/runner.py      match-day and inbox flows used by the buttons
fmauto/catalog.py     list of templates and what to capture
templates/            your captured PNGs
```
