"""Board recognition for Wibble Wobble battles (720x1280 portrait screenshots).

find_wobbles(img)  -> list of Wobble(x, y, r, kind, score)
best_chain(wobbles) -> list of Wobble forming the longest same-kind chain

How it works:
- The board background is dark navy; everything else inside the board circle is a wobble.
- Wobble centres = peaks of the distance transform of that mask.
- Wobble kind = closest colour profile among the 5 team portraits above the board,
  so it adapts to whatever team you bring, no per-Yo-kai images needed.
"""
from dataclasses import dataclass
import time

import cv2
import numpy as np

BOARD_CENTER = (360, 890)
BOARD_RADIUS = 340
# Centres of the 5 team portraits (the arc above the board).
TEAM = [(75, 440), (208, 398), (350, 380), (490, 398), (635, 440)]
REJECT = 0.6  # colour distance above this = unknown (effects, specials)


@dataclass
class Wobble:
    x: int
    y: int
    r: float
    kind: int
    score: float


def _feature(hsv, x, y, r):
    m = np.zeros(hsv.shape[:2], np.uint8)
    cv2.circle(m, (int(x), int(y)), max(int(r), 5), 1, -1)
    px = hsv[m > 0].astype(int)
    h, s, v = px[:, 0], px[:, 1], px[:, 2]
    sat = (s > 90) & (v > 90)
    hist = np.histogram(h[sat], bins=18, range=(0, 180))[0].astype(float)
    pale = float(((s <= 90) & (v > 170)).sum())
    f = np.concatenate([hist, [pale]])
    return f / (f.sum() + 1e-6)


def _hellinger(a, b):
    return float(np.sqrt(((np.sqrt(a) - np.sqrt(b)) ** 2).sum()))


def find_wobbles(img, center=BOARD_CENTER, radius=BOARD_RADIUS, team=TEAM):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)
    navy = (H >= 100) & (H <= 128) & (S > 110) & (V < 150)
    circ = np.zeros(H.shape, np.uint8)
    cv2.circle(circ, tuple(center), radius, 1, -1)
    fg = ((~navy) & (circ > 0)).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    dil = cv2.dilate(dist, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    peaks = ((dist == dil) & (dist > 18)).astype(np.uint8)
    _, _, _, cents = cv2.connectedComponentsWithStats(peaks)

    protos = [_feature(hsv, x - 8, y - 8, 36) for x, y in team]
    out = []
    for cx, cy in cents[1:]:
        x, y = int(cx), int(cy)
        r = float(dist[y, x])
        f = _feature(hsv, x, y, min(r, 40) * 0.85)
        d = [_hellinger(f, p) for p in protos]
        k = int(np.argmin(d))
        out.append(Wobble(x, y, r, k if d[k] <= REJECT else -1, d[k]))
    return out


def _neighbours(ws, gap=30):
    n = len(ws)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = ws[i], ws[j]
            if a.kind < 0 or a.kind != b.kind:
                continue
            if np.hypot(a.x - b.x, a.y - b.y) <= max(a.r, 30) + max(b.r, 30) + gap:
                adj[i].append(j)
                adj[j].append(i)
    return adj


def best_chain(ws, gap=30, time_budget=0.15):
    """Longest simple path of same-kind neighbouring wobbles (DFS with a time budget)."""
    adj = _neighbours(ws, gap)
    best = []
    deadline = time.time() + time_budget

    def dfs(path, seen):
        nonlocal best
        if len(path) > len(best):
            best = list(path)
        if time.time() > deadline:
            return
        for j in adj[path[-1]]:
            if j not in seen:
                seen.add(j)
                path.append(j)
                dfs(path, seen)
                path.pop()
                seen.discard(j)

    # start from nodes with few neighbours first (ends of chains)
    order = sorted(range(len(ws)), key=lambda i: (len(adj[i]) == 0, len(adj[i])))
    for i in order:
        if not adj[i]:
            continue
        dfs([i], {i})
        if time.time() > deadline:
            break
    return [ws[i] for i in best]


COLORS = [(0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 0), (150, 200, 255)]


def draw(img, ws, chain):
    out = img.copy()
    for w in ws:
        c = COLORS[w.kind % len(COLORS)] if w.kind >= 0 else (128, 128, 128)
        cv2.circle(out, (w.x, w.y), 14, c, -1)
    for a, b in zip(chain, chain[1:]):
        cv2.line(out, (a.x, a.y), (b.x, b.y), (255, 255, 255), 5)
    return out


def disjoint_chains(ws, min_len=2, max_chains=4, gap=30, time_budget=0.05):
    """Greedy: longest chain, remove its wobbles, repeat. Longest first."""
    remaining = list(ws)
    chains = []
    while len(chains) < max_chains:
        ch = best_chain(remaining, gap, time_budget)
        if len(ch) < min_len:
            break
        chains.append(ch)
        ids = {id(w) for w in ch}
        remaining = [w for w in remaining if id(w) not in ids]
    return chains


def draw_many(img, ws, chains):
    out = draw(img, ws, [])
    for n, ch in enumerate(chains):
        col = (255, 255, 255) if n == 0 else (0, 255, 255)
        for a, b in zip(ch, ch[1:]):
            cv2.line(out, (a.x, a.y), (b.x, b.y), col, 5)
    return out
