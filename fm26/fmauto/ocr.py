"""OCR helpers (Tesseract) for the score card and the message list."""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract

SCORE_TOKEN = re.compile(r"^(\d{1,2})(?:\s*[-–:]\s*(\d{1,2}))?$")


def configure(tesseract_cmd: str) -> None:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def _prep(img: np.ndarray, scale: int = 2) -> np.ndarray:
    """FM uses light text on dark backgrounds: upscale, grayscale, invert, binarise."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    g = cv2.bitwise_not(g)
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return g


def read_text(img: np.ndarray) -> str:
    return pytesseract.image_to_string(_prep(img), config="--psm 6")


@dataclass
class Score:
    ours: int
    theirs: int
    home: bool


def read_score(img: np.ndarray, crest_x_in_img: int) -> Score | None:
    """Find 'A - B' in img. Our crest's x position tells whether we are home (left) or away."""
    scale = 3
    data = pytesseract.image_to_data(
        _prep(img, scale),
        config="--psm 11 -c tessedit_char_whitelist=0123456789-",
        output_type=pytesseract.Output.DICT,
    )
    digits: list[tuple[float, int]] = []  # (x centre in original px, value)
    for text, left, width in zip(data["text"], data["left"], data["width"]):
        text = text.strip()
        m = SCORE_TOKEN.match(text)
        if not m:
            continue
        cx = (left + width / 2) / scale
        if m.group(2) is not None:  # read as one token "6-0"
            digits += [(cx - 1, int(m.group(1))), (cx + 1, int(m.group(2)))]
        else:
            digits.append((cx, int(m.group(1))))
    if len(digits) < 2:
        return None
    # take the two tokens closest to the middle of the crop (the score sits between the crests)
    mid = img.shape[1] / 2
    digits = sorted(sorted(digits, key=lambda d: abs(d[0] - mid))[:2])
    (lx, left_val), (rx, right_val) = digits
    home = crest_x_in_img < (lx + rx) / 2
    return Score(left_val, right_val, True) if home else Score(right_val, left_val, False)


def classify(score: Score, card_text: str, loss_words: list[str]) -> str:
    if score.ours > score.theirs:
        return "win"
    if score.ours < score.theirs:
        return "loss"
    low = card_text.lower()
    # a draw that knocked us out of a cup (penalties) reads like a defeat in the headline
    if any(w in low for w in loss_words):
        return "loss"
    return "draw"
