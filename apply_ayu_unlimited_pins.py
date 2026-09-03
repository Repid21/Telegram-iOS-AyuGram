#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARK = "AYU_UNLIMITED_PINS_v1"


def die(message: str) -> None:
    print(f"[ayu-unlimited-pins] ERROR: {message}", file=sys.stderr)
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
        print(f"[ayu-unlimited-pins] already patched: {path}")
        return
    updated = transform(text)
    if updated == text:
        die(f"patch produced no changes: {path}")
    path.write_text(updated, encoding="utf-8")
    print(f"[ayu-unlimited-pins] patched: {path}")


def install_helper(root: Path, here: Path) -> None:
    source = here / "payload/AyuUnlimitedPins.swift"
    target = root / "submodules/TelegramCore/Sources/State/AyuUnlimitedPins.swift"
    if not source.is_file():
        die(f"missing helper payload: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[ayu-unlimited-pins] installed helper: {target}")


def patch_toggle(text: str) -> str:
    old = """            let limitCount: Int\n            if case .root = groupId {\n                limitCount = Int(userLimitsConfiguration.maxPinnedChatCount)\n            } else {\n                limitCount = Int(userLimitsConfiguration.maxArchivedPinnedChatCount)\n            }\n"""
    new = """            // AYU_UNLIMITED_PINS_v1: remove Telegram's client-side pin cap.\n            // The synchronizer still sends only the server-supported prefix; overflow pins stay local.\n            let limitCount: Int = Int.max\n"""
    return replace_once(text, old, new, "toggle-limit")


def patch_sync(text: str) -> str:
    old_initial = """    let initialRemoteItemIds = operation.previousItemIds\n    let initialRemoteItemIdsWithoutSecretChats = initialRemoteItemIds.filter { item in\n        switch item {\n            case let .peer(peerId):\n                return peerId.namespace != Namespaces.Peer.SecretChat\n        }\n    }\n"""
    new_initial = """    let initialRemoteItemIds = operation.previousItemIds\n    // AYU_UNLIMITED_PINS_v1: only the account's real server allowance participates\n    // in remote reconciliation. Local overflow must never be interpreted as remotely unpinned.\n    let ayuServerPinnedLimit = AyuUnlimitedPins.serverLimit(transaction: transaction, accountPeerId: accountPeerId, groupId: groupId)\n    let initialRemoteItemIdsWithoutSecretChats = AyuUnlimitedPins.serverVisibleItemIds(initialRemoteItemIds, limit: ayuServerPinnedLimit)\n"""
    text = replace_once(text, old_initial, new_initial, "sync-initial-prefix")

    old_send = """                if remoteItemIds == resultingItemIds {\n                    return .complete()\n                } else {\n                    var inputDialogPeers: [Api.InputDialogPeer] = []\n                    for itemId in resultingItemIds {\n"""
    new_send = """                // AYU_UNLIMITED_PINS_v1: synchronize only the server-visible prefix.\n                // All remaining pinned chats are intentionally local to this installation.\n                let ayuServerResultingItemIds = AyuUnlimitedPins.serverVisibleItemIds(resultingItemIds, limit: ayuServerPinnedLimit)\n                if remoteItemIds == ayuServerResultingItemIds {\n                    return .complete()\n                } else {\n                    var inputDialogPeers: [Api.InputDialogPeer] = []\n                    for itemId in ayuServerResultingItemIds {\n"""
    return replace_once(text, old_send, new_send, "sync-server-prefix")


def patch_reset(text: str) -> str:
    old_capture = """            return withResolvedAssociatedMessages(postbox: postbox, source: .network(network), accountPeerId: accountPeerId, parsedPeers: fetchedChats.peers, storeMessages: fetchedChats.storeMessages, resolveThreads: false, { transaction, additionalPeers, additionalMessages -> Void in\n                for peerId in transaction.chatListGetAllPeerIds() {\n"""
    new_capture = """            return withResolvedAssociatedMessages(postbox: postbox, source: .network(network), accountPeerId: accountPeerId, parsedPeers: fetchedChats.peers, storeMessages: fetchedChats.storeMessages, resolveThreads: false, { transaction, additionalPeers, additionalMessages -> Void in\n                // AYU_UNLIMITED_PINS_v1: capture local pins before reset removes chat-list entries.\n                let ayuLocalPinnedItemIdsBeforeReset = transaction.getPinnedItemIds(groupId: .root)\n                for peerId in transaction.chatListGetAllPeerIds() {\n"""
    text = replace_once(text, old_capture, new_capture, "reset-capture")

    old_set = """                if let replacePinnedItemIds = fetchedChats.pinnedItemIds {\n                    transaction.setPinnedItemIds(groupId: .root, itemIds: replacePinnedItemIds.map(PinnedItemId.peer))\n                }\n"""
    new_set = """                if let replacePinnedItemIds = fetchedChats.pinnedItemIds {\n                    // AYU_UNLIMITED_PINS_v1: server pins stay authoritative at the front,\n                    // while local-only overflow pins survive a full account-state reset.\n                    let remotePinnedItemIds = replacePinnedItemIds.map(PinnedItemId.peer)\n                    let mergedPinnedItemIds = AyuUnlimitedPins.mergeRemoteWithLocalPins(remoteItemIds: remotePinnedItemIds, localItemIds: ayuLocalPinnedItemIdsBeforeReset)\n                    transaction.setPinnedItemIds(groupId: .root, itemIds: mergedPinnedItemIds)\n                }\n"""
    return replace_once(text, old_set, new_set, "reset-merge")


def patch_holes(text: str) -> str:
    old = """            if let replacePinnedItemIds = fetchedChats.pinnedItemIds {\n                transaction.setPinnedItemIds(groupId: groupId, itemIds: replacePinnedItemIds.map(PinnedItemId.peer))\n            }\n"""
    new = """            if let replacePinnedItemIds = fetchedChats.pinnedItemIds {\n                // AYU_UNLIMITED_PINS_v1: filling a chat-list hole must not erase local overflow pins.\n                let remotePinnedItemIds = replacePinnedItemIds.map(PinnedItemId.peer)\n                let localPinnedItemIds = transaction.getPinnedItemIds(groupId: groupId)\n                let mergedPinnedItemIds = AyuUnlimitedPins.mergeRemoteWithLocalPins(remoteItemIds: remotePinnedItemIds, localItemIds: localPinnedItemIds)\n                transaction.setPinnedItemIds(groupId: groupId, itemIds: mergedPinnedItemIds)\n            }\n"""
    return replace_once(text, old, new, "holes-merge")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not (root / "submodules/TelegramCore").is_dir():
        die(f"'{root}' is not TelegramMessenger/Telegram-iOS")
    here = Path(__file__).resolve().parent

    install_helper(root, here)
    patch_file(root / "submodules/TelegramCore/Sources/TelegramEngine/Peers/TogglePeerChatPinned.swift", patch_toggle)
    patch_file(root / "submodules/TelegramCore/Sources/State/ManagedSynchronizePinnedChatsOperations.swift", patch_sync)
    patch_file(root / "submodules/TelegramCore/Sources/State/ResetState.swift", patch_reset)
    patch_file(root / "submodules/TelegramCore/Sources/State/Holes.swift", patch_holes)

    print("[ayu-unlimited-pins] DONE")
    print("[ayu-unlimited-pins] Pins beyond Telegram's server limit are local-only and are not synced to other devices.")


if __name__ == "__main__":
    main()
