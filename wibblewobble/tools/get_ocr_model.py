"""Download MaaFramework's OCR model (det.onnx, rec.onnx, keys.txt) into resource/model/ocr.

Usage (from the project folder):  python tools/get_ocr_model.py
Source: github.com/MaaXYZ/MaaCommonAssets (folder OCR/<version>/zh_cn - reads digits and Latin text fine).
"""
import json
import urllib.request
from pathlib import Path

REPO = "MaaXYZ/MaaCommonAssets"
CANDIDATES = ["OCR/ppocr_v5/zh_cn", "OCR/ppocr_v4/zh_cn"]
FILES = ["det.onnx", "rec.onnx", "keys.txt"]
DEST = Path(__file__).resolve().parent.parent / "resource" / "model" / "ocr"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "wibblewobble-maa"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def list_dir(path: str):
    try:
        data = json.loads(get(f"https://api.github.com/repos/{REPO}/contents/{path}"))
        return {item["name"] for item in data}
    except Exception:
        return set()


def fetch(path: str, name: str) -> bytes:
    data = get(f"https://raw.githubusercontent.com/{REPO}/main/{path}/{name}")
    if data.startswith(b"version https://git-lfs"):
        data = get(f"https://media.githubusercontent.com/media/{REPO}/main/{path}/{name}")
    return data


def main():
    for path in CANDIDATES:
        names = list_dir(path)
        if not all(f in names for f in FILES):
            print(f"skip {path} (found: {sorted(names) or 'nothing'})")
            continue
        DEST.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            print(f"downloading {path}/{f} ...")
            (DEST / f).write_bytes(fetch(path, f))
        print(f"OCR model ready in {DEST}")
        return
    raise SystemExit(
        "Could not find the model automatically. Open https://github.com/MaaXYZ/MaaCommonAssets/tree/main/OCR, "
        "pick the newest ppocr_vX/zh_cn folder and put det.onnx, rec.onnx, keys.txt into resource/model/ocr/."
    )


if __name__ == "__main__":
    main()
