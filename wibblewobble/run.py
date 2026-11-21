"""Run a pipeline task against LDPlayer.

Usage:
    python run.py                        # "Smoke" task: connection test, taps nothing
    python run.py OpenStage              # stamina > 0 ? tap stage 3 (default in map.json)
    python run.py OpenStage --stage 5    # same, but stage 5
    python run.py OpenStage --next       # newest stage (under the yellow arrow)
    python run.py OpenStage --next --smart   # battle with chain recognition (default: random drags)
    python run.py --loop --stage 3       # keep farming stage 3, wait for stamina when out
    python run.py --loop --next --smart  # keep progressing to the newest stage
"""
import argparse
import time

from common import ROOT, connect, load_config, load_resource, make_tasker
from custom import CUSTOM_ACTIONS


def print_detail(detail):
    nodes = getattr(detail, "nodes", None) or []
    for node in nodes:
        reco = getattr(node, "recognition", None)
        best = getattr(reco, "best_result", None) if reco else None
        text = getattr(best, "text", None) if best else None
        box = getattr(best, "box", None) if best else None
        extra = f"  text={text!r}" if text is not None else ""
        extra += f"  box={box}" if box is not None else ""
        print(f"  -> {getattr(node, 'name', node)}{extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", default="Smoke")
    ap.add_argument("--stage", type=int, help="stage number to open on the map")
    ap.add_argument("--next", action="store_true", help="open the newest stage (under the yellow arrow)")
    ap.add_argument("--smart", action="store_true", help="battle: recognise the board and drag the longest chains")
    ap.add_argument("--smart-debug", action="store_true", help="like --smart, also saves annotated boards to debug/smart/")
    ap.add_argument("--loop", action="store_true", help="repeat OpenStage battles; wait when stamina is 0")
    ap.add_argument("--wait", type=int, default=60, help="--loop: seconds between stamina checks when out (default 60)")
    ap.add_argument("--max-fails", type=int, default=3, help="--loop: stop after this many failed runs in a row")
    args = ap.parse_args()
    if args.loop and args.task == "Smoke":
        args.task = "OpenStage"

    override = {}
    if args.stage is not None:
        override["TapStage"] = {"expected": f"^{args.stage}$"}
        digit_img = ROOT / "resource" / "image" / "map_digits" / f"{args.stage}.png"
        if digit_img.exists():
            override["TapStageImg"] = {"enabled": True, "template": f"map_digits/{args.stage}.png"}
        else:
            override["TapStageImg"] = {"enabled": False}

    if args.next:
        override["HasStamina"] = {"next": ["TapArrow"]}
        override["HasStaminaDet"] = {"next": ["TapArrow"]}
    if args.smart or args.smart_debug:
        override["BattleLoop"] = {
            "custom_action": "SmartChains",
            "custom_action_param": {"chains": 4, "random_fill": 1, "debug": bool(args.smart_debug)},
        }

    cfg = load_config()
    controller = connect(cfg)
    resource = load_resource(cfg)
    for name, action in CUSTOM_ACTIONS.items():
        resource.register_custom_action(name, action)
    tasker = make_tasker(resource, controller)

    if args.loop:
        loop(tasker, args, override)
        return

    run_once(tasker, args.task, override, verbose=True)


def node_names(detail):
    return [getattr(n, "name", "") for n in (getattr(detail, "nodes", None) or [])]


def run_once(tasker, task, override, verbose=False):
    """Run one task. Returns (succeeded, node names). Raises KeyboardInterrupt after stopping."""
    print(f"Running task: {task} {override or ''} (Ctrl+C to stop)")
    started = time.time()
    job = tasker.post_task(task, override)
    try:
        detail = job.wait().get()
    except KeyboardInterrupt:
        print("Stopping...")
        tasker.post_stop().wait()
        raise
    ok = job.succeeded
    print(f"Task {task}: {'OK' if ok else 'FAILED'} in {time.time() - started:.1f}s")
    if verbose and detail is not None:
        print_detail(detail)
    return ok, node_names(detail)


def loop(tasker, args, override):
    battles = losses = fails = 0
    started = time.time()
    try:
        while True:
            ok, nodes = run_once(tasker, args.task, override)
            stamp = time.strftime("%H:%M:%S")
            if "LostOrContinue" in nodes:
                print(f"[{stamp}] Unknown lost/retry screen - stopping the loop so nothing gets spent.")
                break
            if "NoStamina" in nodes:
                print(f"[{stamp}] No stamina - checking again in {args.wait}s (Ctrl+C to stop)")
                time.sleep(args.wait)
                continue
            if ok and "BackOnMap" in nodes:
                battles += 1
                lost = "TapNo" in nodes
                losses += lost
                fails = 0
                mins = (time.time() - started) / 60
                result = "LOST (declined Continue)" if lost else "done"
                print(f"[{stamp}] Battle #{battles} {result} ({mins:.0f} min running, {losses} lost)")
                continue
            fails += 1
            print(f"[{stamp}] Run failed ({fails}/{args.max_fails}). Last steps: {nodes[-4:]}")
            if fails >= args.max_fails:
                print("Too many failures in a row - stopping. Check debug/on_error for the screen it got stuck on.")
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    print(f"Loop finished: {battles} battles ({losses} lost).")


if __name__ == "__main__":
    main()
