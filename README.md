# automations-for-games

Game automation scripts. Each project has its own README with setup and usage.

| Project | What it does |
|---|---|
| [fm26](fm26/README.md) | Football Manager 26 + FMRTE: launcher window that triages the inbox and plays matches (template matching + OCR, Windows desktop) |
| [wibblewobble](wibblewobble/README.md) | Yo-kai Watch Wibble Wobble on LDPlayer 9: stage farming and battles via ADB ([MaaFramework](https://maafw.com)) |

Note: the WibbleWobble OCR model is not in the repository. Download it with
`python tools\get_ocr_model.py` from the `wibblewobble` folder (see its README).