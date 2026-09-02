#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARK = "AYU_IOS_EDIT_HISTORY_v1"


def die(message: str) -> None:
    print(f"[ayu-edit-history] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"anchor '{label}' expected exactly once, found {count}")
    return text.replace(old, new, 1)


def replace_all_checked(text: str, old: str, new: str, label: str, minimum: int) -> str:
    count = text.count(old)
    if count < minimum:
        die(f"anchor '{label}' expected at least {minimum}, found {count}")
    print(f"[ayu-edit-history] {label}: {count} replacement(s)")
    return text.replace(old, new)


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + ".ayu-edit-history.bak")
    if not dst.exists():
        shutil.copy2(path, dst)


def patch_file(path: Path, transform) -> None:
    if not path.exists():
        die(f"missing file: {path}")
    text = path.read_text(encoding="utf-8")
    if MARK in text:
        print(f"[ayu-edit-history] already patched: {path}")
        return
    updated = transform(text)
    if updated == text:
        die(f"patch produced no changes: {path}")
    backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[ayu-edit-history] patched: {path}")


def install_payload(source: Path, target: Path) -> None:
    if not source.exists():
        die(f"missing payload: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8"):
        print(f"[ayu-edit-history] payload already installed: {target}")
        return
    if target.exists():
        backup(target)
    shutil.copy2(source, target)
    print(f"[ayu-edit-history] installed: {target}")


def patch_state_replay(text: str) -> str:
    old = """                transaction.updateMessage(id, update: { previousMessage in\n                    var updatedFlags = message.flags\n"""
    new = """                transaction.updateMessage(id, update: { previousMessage in\n                    // AYU_IOS_EDIT_HISTORY_v1: capture the version before a remote edit replaces it.\n                    AyuEditHistoryStore.record(\n                        messageId: id,\n                        previousText: previousMessage.text,\n                        newText: message.text,\n                        validUntil: Int32(Date().timeIntervalSince1970)\n                    )\n                    var updatedFlags = message.flags\n"""
    return replace_once(text, old, new, "central-edit-replay")


def patch_direct_edit_response(text: str) -> str:
    old = """                                            transaction.updateMessage(id, update: { previousMessage in\n                                                var updatedFlags = message.flags\n"""
    new = """                                            transaction.updateMessage(id, update: { previousMessage in\n                                                // AYU_IOS_EDIT_HISTORY_v1: the edit request updates Postbox before AccountStateManager replays the same server update.\n                                                AyuEditHistoryStore.record(\n                                                    messageId: id,\n                                                    previousText: previousMessage.text,\n                                                    newText: message.text,\n                                                    validUntil: Int32(Date().timeIntervalSince1970)\n                                                )\n                                                var updatedFlags = message.flags\n"""
    # Telegram currently has four result variants here (new/edit, regular/channel).
    # All are responses to messages.editMessage; record() itself ignores unchanged text.
    return replace_all_checked(text, old, new, "direct-edit-response", minimum=4)


def patch_context_menu(text: str) -> str:
    old = """        var actions: [ContextMenuItem] = []\n\n        if isSharedMediaPolls && messages.count == 1 {\n"""
    new = """        var actions: [ContextMenuItem] = []\n\n        // AYU_IOS_EDIT_HISTORY_v1: show every locally captured text revision in a submenu.\n        if messages.count == 1, AyuRuntimeSettings.trackEditedMessages {\n            let ayuVersions = AyuEditHistoryStore.versions(for: message.id)\n            if !ayuVersions.isEmpty {\n                actions.append(.action(ContextMenuActionItem(text: \"История изменений\", icon: { _ in\n                    return nil\n                }, action: { c, _ in\n                    var subItems: [ContextMenuItem] = []\n\n                    subItems.append(.action(ContextMenuActionItem(text: chatPresentationInterfaceState.strings.Common_Back, icon: { theme in\n                        return generateTintedImage(image: UIImage(bundleImageName: \"Chat/Context Menu/Back\"), color: theme.actionSheet.primaryTextColor)\n                    }, iconPosition: .left, action: { c, _ in\n                        c?.popItems()\n                    })))\n                    subItems.append(.separator)\n\n                    for (index, version) in ayuVersions.enumerated() {\n                        let versionTitle = index == 0 ? \"Исходный текст\" : \"Версия \\(index + 1)\"\n                        let versionText = version.text.isEmpty ? \"∅\" : version.text\n                        let rowText = \"\\(versionTitle) · до \\(AyuEditHistoryStore.formattedTimestamp(version.validUntil))\\n\\(versionText)\"\n                        subItems.append(.action(ContextMenuActionItem(text: rowText, textLayout: .multiline, textFont: .small, icon: { _ in\n                            return nil\n                        }, action: { _, f in\n                            UIPasteboard.general.string = version.text\n                            f(.default)\n                        })))\n                    }\n\n                    subItems.append(.separator)\n                    let currentText = message.text.isEmpty ? \"∅\" : message.text\n                    subItems.append(.action(ContextMenuActionItem(text: \"Текущая версия\\n\\(currentText)\", textLayout: .multiline, textFont: .small, icon: { _ in\n                        return nil\n                    }, action: { _, f in\n                        UIPasteboard.general.string = message.text\n                        f(.default)\n                    })))\n\n                    c?.pushItems(items: .single(ContextController.Items(content: .list(subItems))))\n                })))\n                actions.append(.separator)\n            }\n        }\n\n        if isSharedMediaPolls && messages.count == 1 {\n"""
    return replace_once(text, old, new, "context-menu")


def apply(repo: Path, payload_root: Path | None = None) -> None:
    root = repo.expanduser().resolve()
    if not (root / "submodules" / "TelegramCore").exists():
        die(f"'{root}' is not TelegramMessenger/Telegram-iOS")

    here = (payload_root or Path(__file__).resolve().parent).resolve()
    state = root / "submodules/TelegramCore/Sources/State"

    install_payload(
        here / "payload" / "AyuEditHistoryStore.swift",
        state / "AyuEditHistoryStore.swift",
    )

    patch_file(state / "AccountStateManagementUtils.swift", patch_state_replay)
    patch_file(root / "submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift", patch_direct_edit_response)
    patch_file(root / "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift", patch_context_menu)

    print("[ayu-edit-history] DONE")


if __name__ == "__main__":
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    apply(repo)
