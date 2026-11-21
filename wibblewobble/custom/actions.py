"""Custom actions for things pipeline JSON can't express on its own.

ChainDrag: press, move through a list of points, release - one continuous finger drag.
That's the basic move for linking Yo-kai on the Wibble Wobble board. Today it takes
fixed points from the pipeline; later a board solver will compute the points itself.

Pipeline usage:
    "action": "Custom",
    "custom_action": "ChainDrag",
    "custom_action_param": {"points": [[200, 800], [300, 850], [400, 800]], "step_ms": 60}
"""
import json
import time

from maa.context import Context
from maa.custom_action import CustomAction


class ChainDrag(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = argv.custom_action_param
        if isinstance(param, str):
            param = json.loads(param or "{}")

        points = param.get("points") or []
        step_ms = int(param.get("step_ms", 60))
        if len(points) < 2:
            print("[ChainDrag] need at least 2 points")
            return False

        ctrl = context.tasker.controller
        x0, y0 = points[0]
        ctrl.post_touch_down(int(x0), int(y0)).wait()
        try:
            for x, y in points[1:]:
                time.sleep(step_ms / 1000)
                ctrl.post_touch_move(int(x), int(y)).wait()
            time.sleep(step_ms / 1000)
        finally:
            ctrl.post_touch_up().wait()
        return True


class RandomChains(CustomAction):
    """Battle filler: N random drags that start somewhere on the board and move
    3-4 wobble-steps toward the board centre. No board recognition yet.

    custom_action_param (all optional):
      {"center": [360, 925], "radius": 300, "drags": 4, "step_px": 70,
       "steps": [3, 4], "move_ms": 40}
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        import math
        import random

        param = argv.custom_action_param
        if isinstance(param, str):
            param = json.loads(param or "{}")
        cx, cy = param.get("center", [360, 900])
        radius = param.get("radius", 300)
        drags = int(param.get("drags", 4))
        step_px = param.get("step_px", 70)
        smin, smax = param.get("steps", [3, 4])
        move_ms = int(param.get("move_ms", 40))

        ctrl = context.tasker.controller
        for _ in range(drags):
            if getattr(context.tasker, "stopping", False):
                break
            # random start inside the board (sqrt -> uniform over the disc)
            ang = random.uniform(0, 2 * math.pi)
            r = radius * math.sqrt(random.uniform(0.15, 1.0))
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)

            ctrl.post_touch_down(int(x), int(y)).wait()
            try:
                for _ in range(random.randint(smin, smax)):
                    dx, dy = cx - x, cy - y
                    dist = math.hypot(dx, dy) or 1
                    # head to the centre with a bit of wobble in direction
                    jitter = random.uniform(-0.6, 0.6)
                    ux, uy = dx / dist, dy / dist
                    ux, uy = ux * math.cos(jitter) - uy * math.sin(jitter), ux * math.sin(jitter) + uy * math.cos(jitter)
                    nx, ny = x + ux * step_px, y + uy * step_px
                    # 3 sub-moves per step so the game registers the path smoothly
                    for i in range(1, 4):
                        ctrl.post_touch_move(int(x + (nx - x) * i / 3), int(y + (ny - y) * i / 3)).wait()
                        time.sleep(move_ms / 3000)
                    x, y = nx, ny
            finally:
                ctrl.post_touch_up().wait()
            time.sleep(random.uniform(0.05, 0.15))
        return True


class SmartChains(CustomAction):
    """Battle with board recognition. One screenshot -> up to `chains` disjoint same-kind
    chains (longest first), dragged back-to-back; then `random_fill` quick random drags.
    Falls back to random drags when nothing chains.

    custom_action_param (all optional):
      {"chains": 4, "min_chain": 2, "random_fill": 1, "seg_ms": 12, "settle_ms": 120, "debug": false}
    debug=true saves annotated boards to debug/smart/.
    """

    _random = RandomChains()

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        from pathlib import Path

        import cv2

        from .board import disjoint_chains, draw_many, find_wobbles

        param = argv.custom_action_param
        if isinstance(param, str):
            param = json.loads(param or "{}")
        max_chains = int(param.get("chains", 4))
        min_chain = int(param.get("min_chain", 2))
        random_fill = int(param.get("random_fill", 1))
        seg_ms = int(param.get("seg_ms", 12))
        settle_ms = int(param.get("settle_ms", 120))
        debug = bool(param.get("debug", False))

        ctrl = context.tasker.controller
        job = ctrl.post_screencap().wait()
        img = job.get() if hasattr(job, "get") else None
        if img is None:
            img = ctrl.cached_image
        if img is None:
            return False

        ws = find_wobbles(img)
        chains = disjoint_chains(ws, min_len=min_chain, max_chains=max_chains)

        if debug:
            out_dir = Path(__file__).resolve().parent.parent / "debug" / "smart"
            out_dir.mkdir(parents=True, exist_ok=True)
            name = f"{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}_" + "-".join(str(len(c)) for c in chains)
            cv2.imwrite(str(out_dir / f"{name or 'none'}.jpg"), draw_many(img, ws, chains))

        for chain in chains:
            if getattr(context.tasker, "stopping", False):
                return True
            pts = [(w.x, w.y) for w in chain]
            ctrl.post_touch_down(*pts[0]).wait()
            try:
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    ctrl.post_touch_move(int((x0 + x1) / 2), int((y0 + y1) / 2)).wait()
                    time.sleep(seg_ms / 2000)
                    ctrl.post_touch_move(int(x1), int(y1)).wait()
                    time.sleep(seg_ms / 2000)
            finally:
                ctrl.post_touch_up().wait()
            time.sleep(0.03)

        fill = random_fill if chains else max(random_fill, 2)
        if fill:
            self._random.run(context, _OneDrag(argv, fill))
        time.sleep(settle_ms / 1000)
        return True


class _OneDrag:
    """Minimal stand-in for RunArg so SmartChains can call RandomChains for one drag."""

    def __init__(self, argv, drags=1):
        self.custom_action_param = {"drags": drags}
        self.box = getattr(argv, "box", None)
        self.node_name = getattr(argv, "node_name", "")
