#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARK = "AYU_HIDE_ADS_v1"


def die(message: str) -> None:
    print(f"[ayu-ads] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"anchor '{label}' expected exactly once, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, transform) -> None:
    if not path.is_file():
        die(f"missing file: {path}")
    text = path.read_text(encoding="utf-8")
    if MARK in text:
        print(f"[ayu-ads] already patched: {path}")
        return
    updated = transform(text)
    if updated == text:
        die(f"patch produced no changes: {path}")
    path.write_text(updated, encoding="utf-8")
    print(f"[ayu-ads] patched: {path}")


def install_helper(root: Path, here: Path) -> None:
    source = here / "payload/AyuAdsSettings.swift"
    target = root / "submodules/TelegramCore/Sources/State/AyuAdsSettings.swift"
    if not source.is_file():
        die(f"missing helper payload: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[ayu-ads] installed helper: {target}")


def patch_ad_messages(text: str) -> str:
    old = """        self.stateValue = State(interPostInterval: nil, messages: [])\n\n        if messageId == nil {\n"""
    new = """        self.stateValue = State(interPostInterval: nil, messages: [])\n\n        // AYU_HIDE_ADS_v1: when enabled, do not restore cached sponsored messages\n        // and do not activate the sponsored-message network context.\n        if AyuAdsSettings.hideAds {\n            self.state.set(.single(State(interPostInterval: nil, messages: [])))\n            return\n        }\n\n        if messageId == nil {\n"""
    return replace_once(text, old, new, "ad-context-short-circuit")


def patch_settings(text: str) -> str:
    text = replace_once(
        text,
        """private enum AyuSettingsPage {\n    case ghost\n    case messages\n    case chats\n}\n""",
        """private enum AyuSettingsPage {\n    case ghost\n    case messages\n    case premium\n    case chats\n}\n""",
        "page-enum",
    )

    text = replace_once(
        text,
        """    case header\n    case ghost(Bool)\n    case messages\n    case chats\n""",
        """    case header\n    case ghost(Bool)\n    case messages\n    case premium\n    case chats\n""",
        "root-entry-enum",
    )

    text = replace_once(
        text,
        """        case .header: return 0\n        case .ghost: return 1\n        case .messages: return 2\n        case .chats: return 3\n""",
        """        case .header: return 0\n        case .ghost: return 1\n        case .messages: return 2\n        case .premium: return 3\n        case .chats: return 4\n""",
        "root-stable-ids",
    )

    chats_block = """        case .chats:\n            return ItemListDisclosureItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"📌  Чаты\",\n                label: \"Закрепления\",\n                sectionId: self.section,\n                style: .blocks,\n                action: { arguments.openPage(.chats) }\n            )\n"""
    premium_and_chats = """        case .premium:\n            return ItemListDisclosureItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"⭐  Клиентский Premium\",\n                label: AyuAdsSettings.hideAds ? \"Реклама отключена\" : \"Доп. функции\",\n                sectionId: self.section,\n                style: .blocks,\n                action: { arguments.openPage(.premium) }\n            )\n""" + chats_block
    text = replace_once(text, chats_block, premium_and_chats, "root-premium-row")

    text = replace_once(
        text,
        """        .ghost(snapshot.master),\n        .messages,\n        .chats\n""",
        """        .ghost(snapshot.master),\n        .messages,\n        .premium,\n        .chats\n""",
        "root-entries",
    )

    text = replace_once(
        text,
        """    case ghost\n    case deleted\n    case edited\n    case chats\n""",
        """    case ghost\n    case deleted\n    case edited\n    case premium\n    case chats\n""",
        "section-enum",
    )

    text = replace_once(
        text,
        """    case editedHeader\n    case trackEdited(Bool)\n    case clearEdited\n\n    case chatsHeader\n""",
        """    case editedHeader\n    case trackEdited(Bool)\n    case clearEdited\n\n    case premiumHeader\n    case hideAds(Bool)\n\n    case chatsHeader\n""",
        "settings-entry-enum",
    )

    text = replace_once(
        text,
        """        case .editedHeader, .trackEdited, .clearEdited:\n            return AyuSettingsSection.edited.rawValue\n        case .chatsHeader, .unlimitedPinsInfo:\n""",
        """        case .editedHeader, .trackEdited, .clearEdited:\n            return AyuSettingsSection.edited.rawValue\n        case .premiumHeader, .hideAds:\n            return AyuSettingsSection.premium.rawValue\n        case .chatsHeader, .unlimitedPinsInfo:\n""",
        "section-routing",
    )

    text = replace_once(
        text,
        """        case .editedHeader: return 40\n        case .trackEdited: return 41\n        case .clearEdited: return 42\n\n        case .chatsHeader: return 60\n""",
        """        case .editedHeader: return 40\n        case .trackEdited: return 41\n        case .clearEdited: return 42\n\n        case .premiumHeader: return 50\n        case .hideAds: return 51\n\n        case .chatsHeader: return 60\n""",
        "settings-stable-ids",
    )

    chats_item = """        case .chatsHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: \"ЗАКРЕПЛЁННЫЕ ЧАТЫ\", sectionId: self.section)\n"""
    premium_items = """        case .premiumHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: \"КЛИЕНТСКИЙ PREMIUM\", sectionId: self.section)\n        case let .hideAds(value):\n            return ItemListSwitchItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"Отключить рекламу\",\n                value: value,\n                sectionId: self.section,\n                style: .blocks,\n                updated: { AyuAdsSettings.setHideAds($0) }\n            )\n\n""" + chats_item
    text = replace_once(text, chats_item, premium_items, "premium-items")

    text = replace_once(
        text,
        """    case .chats:\n        return [\n            .chatsHeader,\n            .unlimitedPinsInfo\n        ]\n""",
        """    case .premium:\n        return [\n            .premiumHeader,\n            .hideAds(AyuAdsSettings.hideAds)\n        ]\n    case .chats:\n        return [\n            .chatsHeader,\n            .unlimitedPinsInfo\n        ]\n""",
        "premium-page-entries",
    )

    text = replace_once(
        text,
        """    case .messages:\n        title = \"Сообщения\"\n    case .chats:\n""",
        """    case .messages:\n        title = \"Сообщения\"\n    case .premium:\n        title = \"Клиентский Premium\"\n    case .chats:\n""",
        "premium-page-title",
    )

    # Marker makes the patch idempotent and documents why the page exists.
    text = text.replace("import AccountContext\n", "import AccountContext\n\n// AYU_HIDE_ADS_v1\n", 1)
    return text


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not (root / "submodules/TelegramCore").is_dir():
        die(f"'{root}' is not TelegramMessenger/Telegram-iOS")
    here = Path(__file__).resolve().parent

    install_helper(root, here)
    patch_file(root / "submodules/TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift", patch_ad_messages)
    patch_file(root / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift", patch_settings)

    print("[ayu-ads] DONE")
    print("[ayu-ads] Toggle location: AyuGram -> Client Premium -> Disable ads")


if __name__ == "__main__":
    main()
