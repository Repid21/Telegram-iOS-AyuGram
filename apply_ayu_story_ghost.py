#!/usr/bin/env python3
"""Protect archived and profile story views when AyuGram Ghost Mode is active.

The existing Ayu v0.3 patch suppresses stories.readStories for feed views.
Telegram iOS calls stories.incrementStoryViews directly for pinned/profile stories;
that direct path must be gated separately.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARK = "AYU_GHOST_STORY_PROFILE_v1"
STORIES = "submodules/TelegramCore/Sources/TelegramEngine/Messages/Stories.swift"

ANCHOR = """func _internal_markStoryAsSeen(account: Account, peerId: PeerId, id: Int32, asPinned: Bool) -> Signal<Never, NoError> {
    if asPinned {
        return account.postbox.transaction { transaction -> Api.InputPeer? in
"""

REPLACEMENT = """func _internal_markStoryAsSeen(account: Account, peerId: PeerId, id: Int32, asPinned: Bool) -> Signal<Never, NoError> {
    if asPinned {
        // AYU_GHOST_STORY_PROFILE_v1: archived and profile story views use
        // stories.incrementStoryViews rather than stories.readStories.
        // Keep the existing local-only regular-story read state unchanged.
        if AyuRuntimeSettings.suppressStoryViews {
            return .complete()
        }
        return account.postbox.transaction { transaction -> Api.InputPeer? in
"""


def apply(root: Path) -> None:
    path = root / STORIES
    if not path.is_file():
        raise RuntimeError(f"Missing Telegram source: {path}")
    source = path.read_text(encoding="utf-8")
    if MARK in source:
        if source.count(MARK) != 1:
            raise RuntimeError(f"Duplicate {MARK} marker in {path}")
        if "if AyuRuntimeSettings.suppressStoryViews" not in source:
            raise RuntimeError("Ghost protection marker exists, but protection is missing")
        print("[ayu-story-ghost] already patched")
        return
    if source.count(ANCHOR) != 1:
        raise RuntimeError(f"Expected exactly one story-view method signature; got {source.count(ANCHOR)}")
    if source.count("Api.functions.stories.incrementStoryViews(peer: inputPeer, id: [id])") != 1:
        raise RuntimeError("Unexpected pinned-story API invocation count")
    result = source.replace(ANCHOR, REPLACEMENT, 1)
    path.write_text(result, encoding="utf-8")
    print("[ayu-story-ghost] protected profile/pinned story views")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cover direct story views in Ayu Ghost Mode")
    parser.add_argument("telegram_repo", type=Path)
    args = parser.parse_args()
    apply(args.telegram_repo.resolve())


if __name__ == "__main__":
    main()
