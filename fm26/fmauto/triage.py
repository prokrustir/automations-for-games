"""Keyword rules for the inbox (same idea as the fm-inbox-triage skill).

OCR sees sender + first line of each message (or the title, in a wide window),
so rules are plain substrings. Anything 'important' stops the auto mark-as-read.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Triage:
    important: list[str] = field(default_factory=list)
    skipped: int = 0

    @property
    def safe_to_mark_read(self) -> bool:
        return not self.important


def classify(lines: list[str], rules: dict) -> Triage:
    keys = [k.lower() for k in rules["important"]]
    excepts = [k.lower() for k in rules["important_exceptions"]]
    t = Triage()
    for line in lines:
        low = line.lower()
        if any(k in low for k in keys) and not any(e in low for e in excepts):
            t.important.append(line)
        else:
            t.skipped += 1
    return t
