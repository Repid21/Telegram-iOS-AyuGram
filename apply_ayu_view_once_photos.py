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
    apply_patch(args.telegram_repo.resolve())


if __name__ == "__main__":
    main()
