# WibbleWobble automation (MaaFramework + LDPlayer 9)

Plays *Yo-kai Watch Wibble Wobble* on LDPlayer automatically: picks a stage, battles,
uses ultimate moves, clicks through results and Yo-kai dialogue, and repeats while
there is stamina. It runs entirely through ADB (screenshots + touches), so the emulator
window can be in the background and nothing on your desktop is clicked.

Built on [MaaFramework](https://maafw.com) (image recognition + OCR + pipeline JSON),
with a few Python custom actions for battles.

---

## 1. Setup

**LDPlayer 9**
- Settings → Advanced → resolution **720 × 1280 (portrait)**. All coordinates and images assume this.
- Settings → Other settings → **ADB debugging: Open local connection**.

**Python (Windows, not WSL)** — run in PowerShell inside this folder:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python tools\get_ocr_model.py       # one-time: OCR model into resource\model\ocr\ (not in the repo)
python run.py                       # smoke test - should end with "Task Smoke: OK"
```
WSL can't see LDPlayer, so it must be Windows Python.

The OCR model (~21 MB) is **not included in the repository** - `tools\get_ocr_model.py` downloads it
from [MaaXYZ/MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets). Without it OCR nodes fail.

---

## 2. Usage

Start with the game on a **stage map** (the screen with numbered stages, Menu / Rankings / Inbox at the bottom).

| Command | What it does |
|---|---|
| `python run.py OpenStage --stage 3` | One battle on stage 3 |
| `python run.py OpenStage --next` | One battle on the newest stage (under the bouncing yellow arrow) |
| `python run.py --loop --stage 3` | Farm stage 3 until stopped |
| `python run.py --loop --next` | Keep progressing through new stages |
| `... --smart` | Battle with chain recognition instead of random drags |
| `... --smart-debug` | Same, and save annotated board images to `debug\smart\` |
| `python run.py BattleLoop` | Start from the middle of a battle |
| `python run.py AfterBattle` | Start from a results / dialogue screen |
| `python capture.py [name]` | Save a 720p screenshot to `screenshots\` (`--loop` for several) |

Loop options: `--wait 60` (seconds between stamina checks when at 0), `--max-fails 3`
(consecutive failed runs before giving up). **Ctrl+C** stops at any time.

### What one run does
```
OpenStage
 ├─ dialogue / OK pop-up over the map? → tap ▼ / OK until gone
 ├─ stamina > 0 ?  ── no ──► NoStamina (run ends; --loop waits and retries)
 └─ yes ► tap stage (number, or yellow arrow with --next) ► tap "Play!"
     ► BattleLoop: while the pause button is visible
          • "Move Ready!" visible? → tap that Yo-kai (ultimate move)
          • otherwise drag wobbles (random, or chains with --smart)
     ► battle over (pause button gone 3× in ~2 s)
     ► repeat until back on the map: tap Next / OK / dialogue ▼ arrow
     ► BackOnMap ✓
```
**Lost battles:** on *"Spend Y-Money to Continue?"* it taps **No** (never Yes), then carries on
through the result screens back to the map; `--loop` counts it as lost and continues.
**Safety:** any other *Give up / Retry / Lost* screen with nothing known to tap stops the task
without tapping anything, and `--loop` ends.

### Loop output
```
[21:40:12] Battle #4 done (11 min running)
[21:41:30] No stamina - checking again in 60s
[21:45:02] Run failed (1/3). Last steps: [...]
```

---

## 3. Battle modes

**Random (default)** — `RandomChains`: 4 drags per round, each starting at a random point
on the board and moving 3–4 wobble-widths towards the centre. Fast, pops lots of wobbles,
good for regular battles.

**Smart (`--smart`)** — `SmartChains` + `custom/board.py`:
1. One screenshot; the board background is a single navy colour, everything else inside
   the board circle is a wobble. Centres come from a distance transform.
2. Each wobble is classified by comparing its colour histogram with the **5 team portraits**
   above the board — it adapts to whatever team you bring, no per-Yo-kai images.
3. Same-kind wobbles that touch form a graph; it takes up to 4 disjoint chains
   (longest first), drags them back-to-back, then adds one random drag.
4. Builds bigger wobbles; slightly slower than random. Tune in `run.py`
   (`"chains"`, `"random_fill"`) or `custom/actions.py` (`seg_ms`, `settle_ms`).

---

## 4. Project layout

| Path | What |
|---|---|
| `run.py` | Entry point: connects, loads resources, applies CLI overrides, runs a task or the loop |
| `common.py` | Finds LDPlayer via ADB, connects, loads the resource bundle |
| `capture.py` | Saves 720p screenshots (for new template images) |
| `config.json` | Optional fixed ADB address / adb path (empty = auto-detect) |
| `config/maa_option.json` | Maa logging. `save_draw: true` writes a debug image per recognition to `debug\vision\` — **large, keep off for loops** |
| `custom/actions.py` | Python actions: `RandomChains`, `SmartChains`, `ChainDrag` (fixed-path drag, unused) |
| `custom/board.py` | Board recognition for `--smart` |
| `resource/pipeline/map.json` | Map: stamina check, stage selection, Play |
| `resource/pipeline/battle.json` | Battle loop, ultimates, end detection, results / dialogue, back to map |
| `resource/default_pipeline.json` | Default delays for every node |
| `resource/image/` | Template images (see below) |
| `resource/model/ocr/` | OCR model (downloaded by `tools/get_ocr_model.py`) |
| `debug/` | `maafw.log`, `on_error/` (full screenshot whenever a run fails) |
| `examples/` | First draft of the stage loop — outdated, kept for reference |

### Pipeline nodes

**map.json**
| Node | Recognises | Does |
|---|---|---|
| `OpenStage` | – | entry point |
| `MapTalk` | `battle/talk_arrow.png` (dialogue ▼ over the map) | tap until the dialogue is gone |
| `MapOk` | OCR "OK" (pop-ups over the map, e.g. *Open Hidden Route*) | tap |
| `HasStamina` / `HasStaminaDet` | OCR on the stamina digit (recognition-only on the digit square, then detection as fallback) | continue |
| `NoStamina` | OCR `0` | end run |
| `TapStage` | OCR stage number (`--stage N`) | tap 70 px above the number |
| `TapStageImg` | `map_digits/N.png` (fallback – OCR often misses single digits) | same |
| `TapArrow` | `map/next_arrow.png` (`--next`, background masked out) | tap the bubble under it |
| `TapPlay` | OCR "Play" | tap |

**battle.json**
| Node | Recognises | Does |
|---|---|---|
| `BattleLoop` | `battle/pause.png` | drag wobbles (custom action) |
| `UseMoveImg` / `UseMove` | `battle/move_ready.png` / OCR "ready" | tap the Yo-kai under the bubble |
| `BattleEnded1..3` | pause button **absent**, 3× ~1 s apart | battle over |
| `BackOnMap` | `map/rankings.png` | end run (checked **before** Next, so the map's wooden "Next" area sign is never tapped) |
| `TapNext` / `TapOk` | OCR "Next" / "OK" | tap |
| `TalkNext` | `battle/talk_arrow.png` (▼ in speech boxes) | tap |
| `ContinuePrompt` → `TapNo` | OCR "Continue" in the dialog, then "No" button | decline paid continue |
| `LostOrContinue` | OCR give up / retry / lost (nothing else tappable) | stop task |
| `AfterBattle` | – | entry point for resuming after a battle |

### Template images (`resource/image/`, 720p, lossless PNG)
| File | Used for |
|---|---|
| `map_digits/1-4,6-8.png` | stage numbers OCR misses (5 and 9+ not cut yet) |
| `map/next_arrow.png` | yellow "next stage" arrow; pure green pixels are ignored (`green_mask`) |
| `map/rankings.png` | "we're on a map" check |
| `battle/pause.png` | "we're in a battle" check |
| `battle/move_ready.png` | ultimate ready bubble |
| `battle/talk_arrow.png` | dialogue advance arrow |

---

## 5. Extending / troubleshooting

**A run fails or gets stuck** → look at `debug\on_error\` (full screenshot of the stuck screen,
named after the node that failed) and `debug\maafw.log` (search for `Recognition.Failed` to
see what OCR read). Typical fixes: widen a `roi`, lower a `threshold`, add a template.

**New screen to handle** (pop-up, event, new button):
1. Get a 720p screenshot (`python capture.py name`, or the automatic one in `debug\on_error\`).
2. Text button → add an OCR node; icon → crop a tight PNG into `resource\image\` and add a
   `TemplateMatch` node. Check it doesn't match other screens.
3. Add the node to the relevant `next` lists (in `battle.json` the after-battle list appears
   in several nodes — keep them identical).

**`--stage N` can't find a number** → crop the digit from a map screenshot into
`resource\image\map_digits\N.png` (tight around the white digit, about 19×22 px).

**Coordinates** are all 720 × 1280. ROI = `[x, y, width, height]`.

### Known limitations
- Single-digit OCR is unreliable, hence the template fallbacks; stage numbers 5 and 9+ have no template yet.
- Event maps (e.g. *Terror Time*) are treated like any map – `--next` will play their newest stage.
- Wobbles partly covered by effects or at the board edge are sometimes missed by `--smart`.

## Pipeline reference
https://maafw.com/en/docs/3.1-PipelineProtocol
