"""Shared helpers: connect to LDPlayer through ADB and load the Maa resource bundle."""
import json
import sys
from pathlib import Path

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parent


def load_config() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def connect(cfg: dict) -> AdbController:
    """Find the emulator via ADB and connect. Maa picks the fastest screencap/input methods itself."""
    # Writes Maa logs to ./debug (maa.log) - look there when something misbehaves.
    Toolkit.init_option(str(ROOT))

    devices = Toolkit.find_adb_devices()
    if not devices:
        sys.exit(
            "No ADB devices found. Is LDPlayer running with "
            "Settings > Other settings > ADB debugging = 'Open local connection'?"
        )

    print("Found devices:")
    for d in devices:
        print(f"  - {d.name}  {d.address}  (adb: {d.adb_path})")

    wanted = cfg.get("adb_address") or ""
    device = next((d for d in devices if wanted and d.address == wanted), None)
    if device is None:
        # Prefer something that looks like LDPlayer, otherwise take the first one.
        device = next((d for d in devices if "ld" in d.name.lower()), devices[0])

    adb_path = cfg.get("adb_path") or device.adb_path
    print(f"Using: {device.name} {device.address}")

    controller = AdbController(
        adb_path=adb_path,
        address=device.address,
        screencap_methods=device.screencap_methods,
        input_methods=device.input_methods,
        config=device.config,
    )
    controller.post_connection().wait()
    if not controller.connected:
        sys.exit("Could not connect to the emulator over ADB.")
    return controller


def load_resource(cfg: dict) -> Resource:
    resource = Resource()
    resource.post_bundle(str(ROOT / cfg.get("resource_dir", "resource"))).wait()
    if not resource.loaded:
        sys.exit("Failed to load resource bundle - check JSON syntax and image paths (see debug/maa.log).")
    return resource


def make_tasker(resource: Resource, controller: AdbController) -> Tasker:
    tasker = Tasker()
    tasker.bind(resource, controller)
    if not tasker.inited:
        sys.exit("Tasker failed to initialise.")
    return tasker
