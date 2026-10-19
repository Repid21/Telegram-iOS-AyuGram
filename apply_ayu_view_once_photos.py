#!/usr/bin/env python3
"""Enable opt-in repeat viewing of incoming view-once photos in cloud chats.

This patch is applied to a pinned Telegram-iOS checkout after the base Ayu
patch. It does not change voice/video content consumption, secret chats,
normal read receipts, or remote server-side deletions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARK = "AYU_VIEW_ONCE_PHOTOS_v1"
SOURCE = "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"

ANCHOR = """        if let message = transaction.getMessage(messageId), message.flags.contains(.Incoming) {
            var updateMessage = false"""

REPLACEMENT = """        if let message = transaction.getMessage(messageId), message.flags.contains(.Incoming) {
            // AYU_VIEW_ONCE_PHOTOS_v1: opt-in, local-only repeat viewing.
            // Do not mark incoming view-once photos consumed or start their
            // removal timer. Leave messages, secret chats and all other media
            // on Telegram's original consumption path.
            if AyuRuntimeSettings.keepViewOncePhotos
                && (message.id.peerId.namespace == Namespaces.Peer.CloudUser
                    || message.id.peerId.namespace == Namespaces.Peer.CloudGroup)
                && message.minAutoremoveOrClearTimeout == viewOnceTimeout
                && message.media.contains(where: { $0 is TelegramMediaImage }) {
                return
            }

            var updateMessage = false"""



SETTINGS = "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def patch_settings(source: str) -> str:
    """Extend the final Ayu Premium settings UI, after apply_ayu_ads.py."""
    source = replace_once(source,
        "    case edited\n    case premium\n    case chats",
        "    case edited\n    case media\n    case premium\n    case chats",
        "media section enum")
    source = replace_once(source,
        "    case clearEdited\n\n    case premiumHeader",
        "    case clearEdited\n\n    case viewOnceHeader\n    case keepViewOncePhotos(Bool)\n\n    case premiumHeader",
        "media entries enum")
    source = replace_once(source,
        "        case .premiumHeader, .hideAds, .premiumIcons:",
        "        case .viewOnceHeader, .keepViewOncePhotos:\n"
        "            return AyuSettingsSection.media.rawValue\n"
        "        case .premiumHeader, .hideAds, .premiumIcons:",
        "media section switch")
    source = replace_once(source,
        "        case .clearEdited: return 42\n\n        case .premiumHeader:",
        "        case .clearEdited: return 42\n\n"
        "        case .viewOnceHeader: return 45\n"
        "        case .keepViewOncePhotos: return 46\n\n"
        "        case .premiumHeader:",
        "media stable ids")
    source = replace_once(source,
        "        case .premiumHeader:\n"
        "            return ItemListSectionHeaderItem(presentationData: presentationData, text:",
        "        // AYU_VIEW_ONCE_PHOTOS_v1: opt-in repeat viewing of incoming photo media.\n"
        "        case .viewOnceHeader:\n"
        "            return ItemListSectionHeaderItem(presentationData: presentationData, text: "
        "\"ОДНОРАЗОВЫЕ ФОТО\", sectionId: self.section)\n"
        "        case let .keepViewOncePhotos(value):\n"
        "            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, "
        "title: \"Повторно открывать одноразовые фото\", value: value, sectionId: self.section, "
        "style: .blocks, updated: { arguments.updateBool(.keepViewOncePhotos, $0) })\n\n"
        "        case .premiumHeader:\n"
        "            return ItemListSectionHeaderItem(presentationData: presentationData, text:",
        "media UI controls")
    source = replace_once(source,
        "            .clearEdited\n        ]",
        "            .clearEdited,\n"
        "            .viewOnceHeader,\n"
        "            .keepViewOncePhotos(snapshot.keepViewOncePhotos)\n"
        "        ]",
        "media page list")
    return source


def apply_patch(root: Path) -> None:
    target = root / SOURCE
    if not target.is_file():
        raise RuntimeError(f"Missing Telegram source: {target}")
    source = target.read_text(encoding="utf-8")
    if MARK in source:
        if source.count(MARK) != 1:
            raise RuntimeError(f"Existing {MARK} marker is duplicated")
        print(f"[ayu-view-once] already patched: {target.name}")
        return
    n = source.count(ANCHOR)
    if n != 1:
        raise RuntimeError(f"Expected exactly one message consumption anchor, got {n}")
    target.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    print(f"[ayu-view-once] patched: {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("telegram_repo", type=Path)
    args = parser.parse_args()
    root = args.telegram_repo.resolve()
    apply_patch(root)
    settings = root / SETTINGS
    if not settings.is_file():
        raise RuntimeError(f"Missing Ayu settings UI: {settings}")
    source = settings.read_text(encoding="utf-8")
    if MARK in source:
        if source.count(MARK) != 1:
            raise RuntimeError("Duplicate view-once settings marker")
        print("[ayu-view-once] settings already patched")
    else:
        settings.write_text(patch_settings(source), encoding="utf-8")
        print("[ayu-view-once] settings patched")



if __name__ == "__main__":
    main()
