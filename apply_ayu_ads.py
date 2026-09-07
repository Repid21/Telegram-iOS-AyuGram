#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARK = "AYU_CLIENT_PREMIUM_v2"


def die(message: str) -> None:
    print(f"[ayu-client-premium] ERROR: {message}", file=sys.stderr)
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
        print(f"[ayu-client-premium] already patched: {path}")
        return
    updated = transform(text)
    if updated == text:
        die(f"patch produced no changes: {path}")
    path.write_text(updated, encoding="utf-8")
    print(f"[ayu-client-premium] patched: {path}")


def install_helper(root: Path, here: Path) -> None:
    source = here / "payload/AyuAdsSettings.swift"
    target = root / "submodules/TelegramCore/Sources/State/AyuAdsSettings.swift"
    if not source.is_file():
        die(f"missing helper payload: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[ayu-client-premium] installed helper: {target}")


def patch_ad_messages(text: str) -> str:
    old_init = """        self.stateValue = State(interPostInterval: nil, messages: [])\n\n        if messageId == nil {\n"""
    new_init = """        self.stateValue = State(interPostInterval: nil, messages: [])\n\n        // AYU_CLIENT_PREMIUM_v2: when ad blocking is already enabled, do not\n        // restore cached sponsored messages and do not start an ad network context.\n        if AyuAdsSettings.hideAds {\n            self.state.set(.single(State(interPostInterval: nil, messages: [])))\n            return\n        }\n\n        if messageId == nil {\n"""
    text = replace_once(text, old_init, new_init, "ad-init-short-circuit")

    old_activate = """    func activate() {\n        if self.isActivated {\n            return\n        }\n        self.isActivated = true\n        \n        let peerId = self.peerId\n"""
    new_activate = """    func activate() {\n        if self.isActivated {\n            return\n        }\n        self.isActivated = true\n\n        // AYU_CLIENT_PREMIUM_v2: manually activated chat contexts must obey the\n        // toggle too (ChatController creates these with activateManually: true).\n        if AyuAdsSettings.hideAds {\n            self.stateValue = State(interPostInterval: nil, messages: [])\n            return\n        }\n        \n        let peerId = self.peerId\n"""
    text = replace_once(text, old_activate, new_activate, "ad-activate-short-circuit")

    old_state = """    public var state: Signal<(interPostInterval: Int32?, messages: [Message], startDelay: Int32?, betweenDelay: Int32?), NoError> {\n        return Signal { subscriber in\n            let disposable = MetaDisposable()\n            \n            self.impl.with { impl in\n                let stateDisposable = impl.state.get().start(next: { state in\n                    subscriber.putNext((state.interPostInterval, state.messages, state.startDelay, state.betweenDelay))\n                })\n                disposable.set(stateDisposable)\n            }\n            \n            return disposable\n        }\n    }\n"""
    new_state = """    public var state: Signal<(interPostInterval: Int32?, messages: [Message], startDelay: Int32?, betweenDelay: Int32?), NoError> {\n        return Signal { subscriber in\n            let disposable = MetaDisposable()\n            \n            self.impl.with { impl in\n                // AYU_CLIENT_PREMIUM_v2: combine the live setting with the context\n                // state. This removes an ad immediately from an already-open chat\n                // instead of requiring the chat/app to be recreated.\n                let stateDisposable = combineLatest(impl.state.get(), AyuAdsSettings.hideAdsSignal).start(next: { state, hideAds in\n                    if hideAds {\n                        subscriber.putNext((nil, [], nil, nil))\n                    } else {\n                        subscriber.putNext((state.interPostInterval, state.messages, state.startDelay, state.betweenDelay))\n                    }\n                })\n                disposable.set(stateDisposable)\n            }\n            \n            return disposable\n        }\n    }\n"""
    text = replace_once(text, old_state, new_state, "ad-live-state-gate")

    old_seen = """    func markAsSeen(opaqueId: Data) {\n        let signal: Signal<Never, NoError> = self.account.network.request(Api.functions.messages.viewSponsoredMessage(randomId: Buffer(data: opaqueId)))\n"""
    new_seen = """    func markAsSeen(opaqueId: Data) {\n        // AYU_CLIENT_PREMIUM_v2: stale UI callbacks must not report hidden ads.\n        if AyuAdsSettings.hideAds {\n            return\n        }\n        let signal: Signal<Never, NoError> = self.account.network.request(Api.functions.messages.viewSponsoredMessage(randomId: Buffer(data: opaqueId)))\n"""
    text = replace_once(text, old_seen, new_seen, "ad-seen-gate")

    old_action = """    func markAction(opaqueId: Data, media: Bool, fullscreen: Bool) {\n        _internal_markAdAction(account: self.account, opaqueId: opaqueId, media: media, fullscreen: fullscreen)\n    }\n"""
    new_action = """    func markAction(opaqueId: Data, media: Bool, fullscreen: Bool) {\n        // AYU_CLIENT_PREMIUM_v2: stale UI callbacks must not click-track hidden ads.\n        if AyuAdsSettings.hideAds {\n            return\n        }\n        _internal_markAdAction(account: self.account, opaqueId: opaqueId, media: media, fullscreen: fullscreen)\n    }\n"""
    return replace_once(text, old_action, new_action, "ad-action-gate")


def patch_theme_settings(text: str) -> str:
    text = replace_once(
        text,
        "import DeviceModel\n",
        "import DeviceModel\n\n// AYU_CLIENT_PREMIUM_v2: local Premium app-icon unlock.\n",
        "theme-marker",
    )

    text = replace_once(
        text,
        """    let premiumConfiguration = PremiumConfiguration.with(appConfiguration: context.currentAppConfiguration.with { $0 })\n    if premiumConfiguration.isPremiumDisabled || context.account.testingEnvironment {\n        appIcons = appIcons.filter { !$0.isPremium } \n    }\n""",
        """    let premiumConfiguration = PremiumConfiguration.with(appConfiguration: context.currentAppConfiguration.with { $0 })\n    if (premiumConfiguration.isPremiumDisabled || context.account.testingEnvironment) && !AyuAdsSettings.unlockPremiumIcons {\n        appIcons = appIcons.filter { !$0.isPremium }\n    }\n""",
        "icon-list-gate",
    )

    text = replace_once(
        text,
        "        let isPremium = peerView.peers[peerView.peerId]?.isPremium ?? false\n",
        "        let isPremium = (peerView.peers[peerView.peerId]?.isPremium ?? false) || AyuAdsSettings.unlockPremiumIcons\n",
        "icon-lock-gate",
    )

    text = replace_once(
        text,
        "            let isPremium = peer?.isPremium ?? false\n",
        "            let isPremium = (peer?.isPremium ?? false) || AyuAdsSettings.unlockPremiumIcons\n",
        "icon-selection-gate",
    )
    return text


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
    premium_and_chats = """        case .premium:\n            return ItemListDisclosureItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"⭐  Клиентский Premium\",\n                label: \"Реклама и иконки\",\n                sectionId: self.section,\n                style: .blocks,\n                action: { arguments.openPage(.premium) }\n            )\n""" + chats_block
    text = replace_once(text, chats_block, premium_and_chats, "root-premium-row")

    text = replace_once(
        text,
        """        .ghost(snapshot.master),\n        .messages,\n        .chats\n""",
        """        .ghost(snapshot.master),\n        .messages,\n        .premium,\n        .chats\n""",
        "root-entries",
    )

    text = replace_once(
        text,
        """    let clearDeleted: () -> Void\n    let clearEdited: () -> Void\n""",
        """    let clearDeleted: () -> Void\n    let clearEdited: () -> Void\n    let updateHideAds: (Bool) -> Void\n    let updatePremiumIcons: (Bool) -> Void\n    let updateUnlimitedPins: (Bool) -> Void\n""",
        "arguments-fields",
    )

    text = replace_once(
        text,
        """        cycleDeletedColor: @escaping () -> Void,\n        clearDeleted: @escaping () -> Void,\n        clearEdited: @escaping () -> Void\n    ) {\n""",
        """        cycleDeletedColor: @escaping () -> Void,\n        clearDeleted: @escaping () -> Void,\n        clearEdited: @escaping () -> Void,\n        updateHideAds: @escaping (Bool) -> Void,\n        updatePremiumIcons: @escaping (Bool) -> Void,\n        updateUnlimitedPins: @escaping (Bool) -> Void\n    ) {\n""",
        "arguments-init-params",
    )

    text = replace_once(
        text,
        """        self.clearDeleted = clearDeleted\n        self.clearEdited = clearEdited\n""",
        """        self.clearDeleted = clearDeleted\n        self.clearEdited = clearEdited\n        self.updateHideAds = updateHideAds\n        self.updatePremiumIcons = updatePremiumIcons\n        self.updateUnlimitedPins = updateUnlimitedPins\n""",
        "arguments-init-assignments",
    )

    text = replace_once(
        text,
        """    case ghost\n    case deleted\n    case edited\n    case chats\n""",
        """    case ghost\n    case deleted\n    case edited\n    case premium\n    case chats\n""",
        "section-enum",
    )

    text = replace_once(
        text,
        """    case editedHeader\n    case trackEdited(Bool)\n    case clearEdited\n\n    case chatsHeader\n    case unlimitedPinsInfo\n""",
        """    case editedHeader\n    case trackEdited(Bool)\n    case clearEdited\n\n    case premiumHeader\n    case hideAds(Bool)\n    case premiumIcons(Bool)\n\n    case chatsHeader\n    case unlimitedPins(Bool)\n    case unlimitedPinsInfo\n""",
        "settings-entry-enum",
    )

    text = replace_once(
        text,
        """        case .editedHeader, .trackEdited, .clearEdited:\n            return AyuSettingsSection.edited.rawValue\n        case .chatsHeader, .unlimitedPinsInfo:\n            return AyuSettingsSection.chats.rawValue\n""",
        """        case .editedHeader, .trackEdited, .clearEdited:\n            return AyuSettingsSection.edited.rawValue\n        case .premiumHeader, .hideAds, .premiumIcons:\n            return AyuSettingsSection.premium.rawValue\n        case .chatsHeader, .unlimitedPins, .unlimitedPinsInfo:\n            return AyuSettingsSection.chats.rawValue\n""",
        "section-routing",
    )

    text = replace_once(
        text,
        """        case .editedHeader: return 40\n        case .trackEdited: return 41\n        case .clearEdited: return 42\n\n        case .chatsHeader: return 60\n        case .unlimitedPinsInfo: return 61\n""",
        """        case .editedHeader: return 40\n        case .trackEdited: return 41\n        case .clearEdited: return 42\n\n        case .premiumHeader: return 50\n        case .hideAds: return 51\n        case .premiumIcons: return 52\n\n        case .chatsHeader: return 60\n        case .unlimitedPins: return 61\n        case .unlimitedPinsInfo: return 62\n""",
        "settings-stable-ids",
    )

    old_chat_items = """        case .chatsHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: \"ЗАКРЕПЛЁННЫЕ ЧАТЫ\", sectionId: self.section)\n        case .unlimitedPinsInfo:\n            return ItemListTextItem(\n                presentationData: presentationData,\n                text: .markdown(\"**Безлимитные закрепы включены.** Можно закреплять больше чатов, чем разрешяет обычный лимит Telegram. Закрепы сверх серверного лимита хранятся только на этом устройстве.\"),\n                sectionId: self.section\n            )\n"""
    new_premium_and_chat_items = """        case .premiumHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: \"КЛИЕНТСКИЙ PREMIUM\", sectionId: self.section)\n        case let .hideAds(value):\n            return ItemListSwitchItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"Отключить рекламу\",\n                value: value,\n                sectionId: self.section,\n                style: .blocks,\n                updated: { arguments.updateHideAds($0) }\n            )\n        case let .premiumIcons(value):\n            return ItemListSwitchItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"Разблокировать Premium-иконки\",\n                value: value,\n                sectionId: self.section,\n                style: .blocks,\n                updated: { arguments.updatePremiumIcons($0) }\n            )\n\n        case .chatsHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: \"ЗАКРЕПЛЁННЫЕ ЧАТЫ\", sectionId: self.section)\n        case let .unlimitedPins(value):\n            return ItemListSwitchItem(\n                presentationData: presentationData,\n                systemStyle: .glass,\n                title: \"Безлимитные закрепы\",\n                value: value,\n                sectionId: self.section,\n                style: .blocks,\n                updated: { arguments.updateUnlimitedPins($0) }\n            )\n        case .unlimitedPinsInfo:\n            return ItemListTextItem(\n                presentationData: presentationData,\n                text: .markdown(\"При включении можно закреплять больше чатов, чем разрешает обычный лимит Telegram. Закрепы сверх серверного лимита хранятся только на этом устройстве.\"),\n                sectionId: self.section\n            )\n"""
    text = replace_once(text, old_chat_items, new_premium_and_chat_items, "premium-and-chat-items")

    text = replace_once(
        text,
        """    case .chats:\n        return [\n            .chatsHeader,\n            .unlimitedPinsInfo\n        ]\n""",
        """    case .premium:\n        return [\n            .premiumHeader,\n            .hideAds(AyuAdsSettings.hideAds),\n            .premiumIcons(AyuAdsSettings.unlockPremiumIcons)\n        ]\n    case .chats:\n        return [\n            .chatsHeader,\n            .unlimitedPins(AyuUnlimitedPins.isEnabled),\n            .unlimitedPinsInfo\n        ]\n""",
        "page-entries",
    )

    text = replace_once(
        text,
        """        clearEdited: {\n            AyuEditHistoryStore.clearAll()\n            bump()\n        }\n    )\n""",
        """        clearEdited: {\n            AyuEditHistoryStore.clearAll()\n            bump()\n        },\n        updateHideAds: { value in\n            AyuAdsSettings.setHideAds(value)\n            bump()\n        },\n        updatePremiumIcons: { value in\n            AyuAdsSettings.setUnlockPremiumIcons(value)\n            bump()\n        },\n        updateUnlimitedPins: { value in\n            AyuUnlimitedPins.setEnabled(value)\n            if !value {\n                let _ = AyuUnlimitedPins.trimToServerLimits(postbox: context.account.postbox, accountPeerId: context.account.peerId).start()\n            }\n            bump()\n        }\n    )\n""",
        "arguments-actions",
    )

    text = replace_once(
        text,
        """    case .messages:\n        title = \"Сообщения\"\n    case .chats:\n""",
        """    case .messages:\n        title = \"Сообщения\"\n    case .premium:\n        title = \"Клиентский Premium\"\n    case .chats:\n""",
        "premium-page-title",
    )

    text = text.replace("import AccountContext\n", "import AccountContext\n\n// AYU_CLIENT_PREMIUM_v2\n", 1)
    return text


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not (root / "submodules/TelegramCore").is_dir():
        die(f"'{root}' is not TelegramMessenger/Telegram-iOS")
    here = Path(__file__).resolve().parent

    install_helper(root, here)
    patch_file(root / "submodules/TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift", patch_ad_messages)
    patch_file(root / "submodules/SettingsUI/Sources/Themes/ThemeSettingsController.swift", patch_theme_settings)
    patch_file(root / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift", patch_settings)

    print("[ayu-client-premium] DONE")
    print("[ayu-client-premium] Toggles: AyuGram -> Client Premium; unlimited pins: AyuGram -> Chats")


if __name__ == "__main__":
    main()
