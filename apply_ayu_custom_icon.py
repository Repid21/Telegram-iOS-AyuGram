#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MARK = "AYU_CUSTOM_ICON_v1"
ICON_NAME = "AyuCustom"


def die(message: str) -> None:
    print(f"[ayu-custom-icon] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"anchor '{label}' expected exactly once, found {count}")
    return text.replace(old, new, 1)


def patch_build_file(root: Path) -> None:
    path = root / "Telegram/BUILD"
    text = path.read_text(encoding="utf-8")
    if f'    "{ICON_NAME}",' in text:
        print("[ayu-custom-icon] Telegram/BUILD already patched")
        return

    old = '    "BlueFilledIcon",\n    "WhiteFilledIcon",'
    new = f'    "BlueFilledIcon",\n    "{ICON_NAME}",\n    "WhiteFilledIcon",'
    text = replace_once(text, old, new, "alternate-icon-list")
    path.write_text(text, encoding="utf-8")
    print("[ayu-custom-icon] patched Telegram/BUILD")


def patch_app_delegate(root: Path) -> None:
    path = root / "submodules/TelegramUI/Sources/AppDelegate.swift"
    text = path.read_text(encoding="utf-8")
    if f'PresentationAppIcon(name: "{ICON_NAME}"' in text:
        print("[ayu-custom-icon] AppDelegate already patched")
        return

    old = '                    PresentationAppIcon(name: "BlackFilledIcon", imageName: "BlackFilledIcon")\n'
    new = (
        '                    PresentationAppIcon(name: "BlackFilledIcon", imageName: "BlackFilledIcon"),\n'
        f'                    PresentationAppIcon(name: "{ICON_NAME}", imageName: "{ICON_NAME}")\n'
    )
    text = replace_once(text, old, new, "app-icon-entry")
    path.write_text(text, encoding="utf-8")
    print("[ayu-custom-icon] patched AppDelegate.swift")


def patch_icon_title(root: Path) -> None:
    path = root / "submodules/SettingsUI/Sources/Themes/ThemeSettingsAppIconItem.swift"
    text = path.read_text(encoding="utf-8")
    if f'case "{ICON_NAME}":' in text:
        print("[ayu-custom-icon] icon title already patched")
        return

    old = (
        '                                case "PremiumTurbo":\n'
        '                                    name = item.strings.Appearance_AppIconTurbo\n'
        '                                default:\n'
        '                                    name = icon.name\n'
    )
    new = (
        '                                case "PremiumTurbo":\n'
        '                                    name = item.strings.Appearance_AppIconTurbo\n'
        f'                                case "{ICON_NAME}":\n'
        '                                    name = "Своя"\n'
        '                                default:\n'
        '                                    name = icon.name\n'
    )
    text = replace_once(text, old, new, "custom-icon-title")
    path.write_text(text, encoding="utf-8")
    print("[ayu-custom-icon] patched ThemeSettingsAppIconItem.swift")


def create_placeholder_icon(root: Path) -> Path:
    source = root / "Telegram/Telegram-iOS/New1.alticon"
    target = root / f"Telegram/Telegram-iOS/{ICON_NAME}.alticon"
    if not source.is_dir():
        die(f"missing source alternate icon folder: {source}")

    target.mkdir(parents=True, exist_ok=True)
    for source_file in source.glob("*.png"):
        target_name = source_file.name.replace("New1", ICON_NAME, 1)
        target_file = target / target_name
        if not target_file.exists():
            shutil.copy2(source_file, target_file)

    print(f"[ayu-custom-icon] custom icon slot ready: {target}")
    return target


def find_custom_source(here: Path) -> Path | None:
    for name in ("AyuCustomIcon.png", "AyuCustomIcon.jpg", "AyuCustomIcon.jpeg"):
        candidate = here / "payload" / name
        if candidate.is_file():
            return candidate
    return None


def sips_value(path: Path, key: str) -> int:
    output = subprocess.check_output(["sips", "-g", key, str(path)], text=True)
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(f"{key}:"):
            return int(float(line.split(":", 1)[1].strip()))
    die(f"could not read {key} from {path}")
    return 0


def render_custom_icon(source: Path, target: Path) -> None:
    if shutil.which("sips") is None:
        print("[ayu-custom-icon] custom image found, but 'sips' is unavailable; keeping placeholder")
        return

    sizes = {
        f"{ICON_NAME}@2x.png": 120,
        f"{ICON_NAME}@3x.png": 180,
        f"{ICON_NAME}_29x29.png": 29,
        f"{ICON_NAME}_58x58.png": 58,
        f"{ICON_NAME}_80x80.png": 80,
        f"{ICON_NAME}_87x87.png": 87,
        f"{ICON_NAME}-76.png": 76,
        f"{ICON_NAME}-76@2x.png": 152,
        f"{ICON_NAME}-83.5@2x.png": 167,
        f"{ICON_NAME}_notification.png": 20,
        f"{ICON_NAME}_notification@2x.png": 40,
        f"{ICON_NAME}_notification@3x.png": 60,
    }

    with tempfile.TemporaryDirectory(prefix="ayu-custom-icon-") as tmp:
        converted = Path(tmp) / "converted.png"
        cropped = Path(tmp) / "cropped.png"

        subprocess.run(
            ["sips", "-s", "format", "png", str(source), "--out", str(converted)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        width = sips_value(converted, "pixelWidth")
        height = sips_value(converted, "pixelHeight")
        side = min(width, height)
        if side <= 0:
            die("custom icon has invalid dimensions")

        subprocess.run(
            ["sips", "-c", str(side), str(side), str(converted), "--out", str(cropped)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        for filename, size in sizes.items():
            subprocess.run(
                ["sips", "-z", str(size), str(size), str(cropped), "--out", str(target / filename)],
                check=True,
                stdout=subprocess.DEVNULL,
            )

    print(f"[ayu-custom-icon] rendered custom icon from: {source}")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not (root / "Telegram/BUILD").is_file():
        die(f"'{root}' is not TelegramMessenger/Telegram-iOS")

    here = Path(__file__).resolve().parent

    patch_build_file(root)
    patch_app_delegate(root)
    patch_icon_title(root)
    target = create_placeholder_icon(root)

    custom_source = find_custom_source(here)
    if custom_source is not None:
        render_custom_icon(custom_source, target)
    else:
        print("[ayu-custom-icon] payload/AyuCustomIcon.(png|jpg|jpeg) not found; using placeholder icon")

    print(f"[ayu-custom-icon] DONE ({MARK})")


if __name__ == "__main__":
    main()
