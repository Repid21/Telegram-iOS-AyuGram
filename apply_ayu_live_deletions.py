#!/usr/bin/env python3
"""Refresh visible Telegram iOS message status nodes on Ayu deletion changes.

Run AFTER apply_ayu_v03_crashfix.py. The pinned Telegram checkout is patched
rather than duplicated in this small Ayu overlay repository.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARK = "AYU_LIVE_DELETED_MARKERS_v1"
STATUS = "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/ChatMessageDateAndStatusNode.swift"
CHAT_COMPONENTS = {
    "ChatMessageStickerItemNode": "item.message.id",
    "ChatMessageMapBubbleContentNode": "item.message.id",
    "ChatMessageAttachedContentNode": "message.id",
    "ChatMessageInteractiveFileNode": "arguments.message.id",
    "ChatMessageInteractiveMediaNode": "message.id",
    "ChatMessageTextBubbleContentNode": "item.message.id",
    "ChatMessageContactBubbleContentNode": "item.message.id",
    "ChatMessageTodoBubbleContentNode": "item.message.id",
    "ChatMessageAnimatedStickerItemNode": "item.message.id",
    "ChatMessagePollBubbleContentNode": "item.message.id",
    "ChatMessageRestrictedBubbleContentNode": "item.message.id",
    "ChatMessageRichDataBubbleContentNode": "item.message.id",
    "ChatMessageGiveawayBubbleContentNode": "item.message.id",
    "ChatMessageFactCheckBubbleContentNode": "item.message.id",
    "ChatMessageInteractiveInstantVideoNode": "item.message.id",
}


def replace_once(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return src.replace(old, new, 1)


def patch_status(src: str) -> str:
    src = replace_once(src, "        var dateText: String\n", "        var dateText: String\n        var messageId: MessageId?\n", "status.arguments.property")
    src = replace_once(src, "            dateText: String,\n", "            dateText: String,\n            messageId: MessageId? = nil,\n", "status.arguments.init")
    src = replace_once(src, "            self.dateText = dateText\n", "            self.dateText = dateText\n            self.messageId = messageId\n", "status.arguments.assignment")

    src = replace_once(src, "    private var layoutSize: CGSize?\n", """    private var layoutSize: CGSize?

    // AYU_LIVE_DELETED_MARKERS_v1: reuse the existing status layout for visible cells.
    private var ayuLastStatusArguments: Arguments?
    private var ayuLastStatusBoundingWidth: CGFloat = 0.0

    @objc private func ayuDeletedMarkersChanged() {
        // Notifications arrive on the main queue. Do not query Telegram or re-enter a chat.
        guard let previous = self.ayuLastStatusArguments,
              let messageId = previous.messageId else {
            return
        }
        let baseText = AyuRuntimeSettings.undecorateTimestamp(previous.dateText)
        let nextText = AyuRuntimeSettings.decorateTimestamp(baseText, messageId: messageId)
        // Refresh the color too when the user changes marker appearance.
        if nextText == previous.dateText && !AyuRuntimeSettings.isDeleted(messageId) {
            return
        }
        var updated = previous
        updated.dateText = nextText
        let (_, continueLayout) = self.asyncLayout()(updated)
        let (_, apply) = continueLayout(self.ayuLastStatusBoundingWidth)
        apply(.None)
    }
""", "status.node.state")
    src = replace_once(src, "        self.addSubnode(self.dateNode)\n    }\n", """        self.addSubnode(self.dateNode)
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(self.ayuDeletedMarkersChanged),
            name: AyuRuntimeSettings.deletedMarkersChangedNotification,
            object: nil
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self, name: AyuRuntimeSettings.deletedMarkersChangedNotification, object: nil)
    }
""", "status.node.observer")
    src = replace_once(src, "                        strongSelf.layoutSize = layoutSize\n", """                        strongSelf.layoutSize = layoutSize
                        strongSelf.ayuLastStatusArguments = arguments
                        strongSelf.ayuLastStatusBoundingWidth = boundingWidth
""", "status.node.apply")
    return src


def patch_component(src: str, message_id: str, label: str) -> str:
    start = src.find("ChatMessageDateAndStatusNode.Arguments(")
    if start < 0 or src.count("ChatMessageDateAndStatusNode.Arguments(") != 1:
        raise RuntimeError(f"{label}: expected one status arguments initializer")
    needle = "dateText: "
    date_start = src.find(needle, start)
    if date_start < 0:
        raise RuntimeError(f"{label}: missing dateText field")
    date_end = src.find("\n", date_start)
    if date_end < 0 or date_end > date_start + 110 or not src[date_start:date_end].rstrip().endswith(","):
        raise RuntimeError(f"{label}: unexpected dateText field")
    # Match the call's indentation instead of hardcoding Swift whitespace.
    line_start = src.rfind("\n", 0, date_start) + 1
    indentation = src[line_start:date_start]
    if not indentation.isspace():
        raise RuntimeError(f"{label}: malformed indentation")
    insertion = indentation + f"messageId: {message_id}, // {MARK}\n"
    return src[:date_end+1] + insertion + src[date_end+1:]


def patch(path: Path, transform) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing Telegram source: {path}")
    original = path.read_text(encoding="utf-8")
    if MARK in original:
        print(f"[ayu-live-delete] already patched: {path.name}")
        return
    changed = transform(original)
    if changed == original:
        raise RuntimeError(f"no changes in {path}")
    path.write_text(changed, encoding="utf-8")
    print(f"[ayu-live-delete] patched: {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("telegram_repo", type=Path)
    args = parser.parse_args()
    root = args.telegram_repo.resolve()
    patch(root / STATUS, patch_status)
    component_root = root / "submodules/TelegramUI/Components/Chat"
    for component, message_id in CHAT_COMPONENTS.items():
        file = component_root / component / "Sources" / (component + ".swift")
        patch(file, lambda src, mid=message_id, name=component: patch_component(src, mid, name))
    print("[ayu-live-delete] DONE: all 15 message status layouts support live deletion marks")


if __name__ == "__main__":
    main()
