#!/usr/bin/env python3
from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=str(cwd) if cwd else None, check=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parent)).resolve()
    runner_temp = Path(os.environ.get("RUNNER_TEMP", "/tmp")).resolve()
    telegram = runner_temp / "Telegram-iOS"

    print("=== Python syntax ===", flush=True)
    patchers = (
        "apply_ayu_v03.py",
        "apply_ayu_v03_fixed.py",
        "apply_ayu_v03_crashfix.py",
        "apply_ayu_edit_history.py",
        "apply_ayu_profile_cache.py",
        "apply_ayu_unlimited_pins.py",
        "apply_ayu_ads.py",
        "apply_ayu_live_deletions.py",
        "apply_ayu_view_once_photos.py",
        "apply_ayu_transcription.py",
        "apply_ayu_story_ghost.py",
        "apply_ayu_deleted_forward.py",
        "apply_ayu_network.py",
    )
    for name in patchers:
        py_compile.compile(str(workspace / name), doraise=True)
        print(f"OK: {name}")

    ref = (workspace / "telegram-ref.txt").read_text(encoding="utf-8").strip()
    require(bool(ref), "telegram-ref.txt is empty")

    print("=== Checkout pinned Telegram source ===", flush=True)
    shutil.rmtree(telegram, ignore_errors=True)
    run("git", "init", str(telegram))
    run("git", "remote", "add", "origin", "https://github.com/TelegramMessenger/Telegram-iOS.git", cwd=telegram)
    run("git", "fetch", "--depth", "1", "origin", ref, cwd=telegram)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=telegram)
    actual_ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=telegram, text=True).strip()
    require(actual_ref == ref, f"Pinned Telegram ref mismatch: {actual_ref} != {ref}")
    print(f"Telegram ref: {actual_ref}")

    print("=== Apply Ayu patches ===", flush=True)
    run(sys.executable, str(workspace / "apply_ayu_v03_crashfix.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_live_deletions.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_live_deletions.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_profile_cache.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_unlimited_pins.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_ads.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_view_once_photos.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_view_once_photos.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_transcription.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_transcription.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_story_ghost.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_story_ghost.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_deleted_forward.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_deleted_forward.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_network.py"), str(telegram))
    run(sys.executable, str(workspace / "apply_ayu_network.py"), str(telegram))

    print("=== Verify network enhancements ===", flush=True)
    for relative in (
        "submodules/TelegramCore/Sources/Network/MultipartUpload.swift",
        "submodules/TelegramCore/Sources/Network/FetchV2.swift",
        "submodules/TelegramCore/Sources/Network/MultipartFetch.swift",
        "submodules/TelegramCore/Sources/Account/Account.swift",
        "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift",
        "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift",
        "submodules/BrowserUI/Sources/BrowserWebContent.swift",
    ):
        require((telegram / relative).read_text(encoding="utf-8").count("AYU_NETWORK_TOOLS_v1") == 1, f"network overlay missing/duplicated: {relative}")
    network_helper = (telegram / "submodules/TelegramCore/Sources/State/AyuNetworkSettings.swift").read_text(encoding="utf-8")
    require("ProxyServersStatuses" in network_helper and "skipAutomaticProxy" in network_helper, "native proxy monitor or VPN guard missing")
    require("URLSessionConfiguration.ephemeral" in network_helper and 'url.scheme?.lowercased() == "https"' in network_helper, "proxy feed privacy guard missing")
    require("latest == observed" in network_helper, "manual proxy change protection missing")
    require("registrationMonth" in network_helper, "registration formatter missing")

    print("=== Verify native settings ===", flush=True)
    settings = (telegram / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoSettingsItems.swift").read_text(encoding="utf-8")
    marker = 'text: "AyuGram"'
    photo = "items[.edit]!.append(PeerInfoScreenActionItem(id: 2,"
    username = 'if let peer = data.peer, (peer.addressName ?? "").isEmpty {'
    require(settings.count(marker) == 1, "AyuGram settings row missing or duplicated")
    require(photo in settings, "profile photo row anchor missing")
    require(username in settings, "My Profile row anchor missing")
    require(settings.index(photo) < settings.index(marker) < settings.index(username), "AyuGram row is not between profile photo and My Profile")

    peer_info_root = telegram / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources"
    state_root = telegram / "submodules/TelegramCore/Sources/State"
    require((peer_info_root / "AyuSettingsController.swift").exists(), "AyuSettingsController.swift missing")
    require((peer_info_root / "AyuProfileFieldCache.swift").exists(), "AyuProfileFieldCache.swift missing")
    require((state_root / "AyuGhostLastSeen.swift").exists(), "AyuGhostLastSeen.swift missing")
    require((state_root / "AyuEditHistoryStore.swift").exists(), "AyuEditHistoryStore.swift missing")
    require((state_root / "AyuUnlimitedPins.swift").exists(), "AyuUnlimitedPins.swift missing")
    require((state_root / "AyuAdsSettings.swift").exists(), "AyuAdsSettings.swift missing")

    debug = (telegram / "submodules/DebugSettingsUI/Sources/DebugController.swift").read_text(encoding="utf-8")
    require("AyuGram Settings" not in debug, "legacy DebugController Ayu row is still being injected")

    print("=== Verify Ghost read crash fix ===", flush=True)
    read_state = (state_root / "SynchronizePeerReadState.swift").read_text(encoding="utf-8")
    require("Ghost read suppression must remove the Postbox" in read_state, "transaction-safe Ghost read marker missing")
    require("transaction.confirmSynchronizedIncomingReadState(peerId)" in read_state, "Ghost read operation is not consumed through Postbox")
    require("if validate && !AyuRuntimeSettings.suppressReadMessages" not in read_state, "old validation no-op recursion path is still present")
    dangerous = "if AyuRuntimeSettings.suppressReadMessages {\n        return .single(readState)"
    require(dangerous not in read_state, "old synchronous .single(readState) Ghost shortcut is still present")

    print("=== Verify complete anonymous story viewing ===", flush=True)
    regular_stories = (state_root / "ManagedSynchronizeViewStoriesOperations.swift").read_text(encoding="utf-8")
    profile_stories = (telegram / "submodules/TelegramCore/Sources/TelegramEngine/Messages/Stories.swift").read_text(encoding="utf-8")
    story_ui = (telegram / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift").read_text(encoding="utf-8")
    require("if AyuRuntimeSettings.suppressStoryViews" in regular_stories, "regular story views are not suppressed")
    require(regular_stories.index("if AyuRuntimeSettings.suppressStoryViews") < regular_stories.index("Api.functions.stories.readStories"), "regular story gate comes after network read")
    require(profile_stories.count("AYU_GHOST_STORY_PROFILE_v1") == 1, "profile story protection missing/duplicated")
    pinned_scope = profile_stories.split("func _internal_markStoryAsSeen", 1)[1].split("func _internal_updateStoriesArePinned", 1)[0]
    require(pinned_scope.index("if AyuRuntimeSettings.suppressStoryViews") < pinned_scope.index("Api.functions.stories.incrementStoryViews"), "pinned story view gate missing")
    require("Анонимный просмотр историй" in story_ui, "Ghost Mode story switch missing")
    require("arguments.updateBool(.hideReadStories, $0)" in story_ui, "Ghost story switch not wired")
    require("return state.with { $0.master && $0.hideReadStories }" in (state_root / "AyuRuntimeSettings.swift").read_text(encoding="utf-8"), "story views not guarded by Ghost master setting")

    print("=== Verify deleted-message hooks ===", flush=True)
    state_utils = (state_root / "AccountStateManagementUtils.swift").read_text(encoding="utf-8")
    require(state_utils.count("AyuRuntimeSettings.markDeletedGlobalIds") >= 1, "global deleted-message hook missing")
    require(state_utils.count("AyuRuntimeSettings.markDeletedMessageIds") >= 2, "channel deleted-message hooks missing")
    require("AyuRuntimeSettings.keepDeletedMessages" in state_utils, "deleted preservation guard missing")

    print("=== Verify live deleted-message UI ===", flush=True)
    runtime = (state_root / "AyuRuntimeSettings.swift").read_text(encoding="utf-8")
    require("AYU_LIVE_DELETED_MARKERS_v1" in runtime, "deleted marker notifications missing")
    require(runtime.count("notifyDeletedMarkersChanged()") >= 6, "deleted message and style hooks not reactive")
    status = (telegram / "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/ChatMessageDateAndStatusNode.swift").read_text(encoding="utf-8")
    for needle in (
        "AYU_LIVE_DELETED_MARKERS_v1",
        "messageId: MessageId? = nil",
        "ayuDeletedMarkersChanged()",
        "strongSelf.ayuLastStatusArguments = arguments",
        "AyuRuntimeSettings.deletedMarkersChangedNotification",
    ):
        require(needle in status, f"live deleted-status hook missing: {needle}")
    from apply_ayu_live_deletions import CHAT_COMPONENTS
    for component in CHAT_COMPONENTS:
        path = telegram / "submodules/TelegramUI/Components/Chat" / component / "Sources" / (component + ".swift")
        content = path.read_text(encoding="utf-8")
        require(content.count("AYU_LIVE_DELETED_MARKERS_v1") == 1, f"live status message binding missing/duplicated: {component}")

    print("=== Verify repeat view-once photos ===", flush=True)
    consumed = (telegram / "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift").read_text(encoding="utf-8")
    require(consumed.count("AYU_VIEW_ONCE_PHOTOS_v1") == 1, "repeat view-once photo hook missing/duplicated")
    require("if AyuRuntimeSettings.keepViewOncePhotos" in consumed, "view-once photo gate missing")
    require("message.minAutoremoveOrClearTimeout == viewOnceTimeout" in consumed, "view-once timeout filter missing")
    require("message.media.contains(where: { $0 is TelegramMediaImage })" in consumed, "image-only filter missing")
    require("message.id.peerId.namespace == Namespaces.Peer.CloudUser" in consumed, "user cloud scope missing")
    require("message.id.peerId.namespace == Namespaces.Peer.CloudGroup" in consumed, "group cloud scope missing")
    # The usual consumption operations must still exist for all other media.
    require("addSynchronizeConsumeMessageContentsOperation(transaction: transaction, messageIds: [message.id])" in consumed, "normal consumed operations unexpectedly removed")
    require("AutoclearTimeoutMessageAttribute(timeout: timeout, countdownBeginTime: timestamp)" in consumed, "normal timeout logic unexpectedly removed")
    runtime = (state_root / "AyuRuntimeSettings.swift").read_text(encoding="utf-8")
    settings_controller = (peer_info_root / "AyuSettingsController.swift").read_text(encoding="utf-8")
    require("case keepViewOncePhotos = 10" in runtime, "view-once settings case missing")
    require("keepViewOncePhotos: storedValue(.keepViewOncePhotos, defaults: defaults)" in runtime, "view-once settings persistence missing")
    require("case .keepViewOncePhotos:" in runtime and "return false" in runtime, "view-once must default off")
    require("Повторно открывать одноразовые фото" in settings_controller, "view-once UI switch missing")
    require("arguments.updateBool(.keepViewOncePhotos, $0)" in settings_controller, "view-once UI action missing")

    print("=== Verify optional on-device voice transcription ===", flush=True)
    runtime = (state_root / "AyuRuntimeSettings.swift").read_text(encoding="utf-8")
    settings_controller = (peer_info_root / "AyuSettingsController.swift").read_text(encoding="utf-8")
    voice_node = (telegram / "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveFileNode/Sources/ChatMessageInteractiveFileNode.swift").read_text(encoding="utf-8")
    speech_node = (telegram / "submodules/Media/LocalAudioTranscription/Sources/LocalAudioTranscription.swift").read_text(encoding="utf-8")
    require("case localVoiceTranscription = 11" in runtime, "local transcription setting missing")
    require("localVoiceTranscription: storedValue(.localVoiceTranscription, defaults: defaults)" in runtime, "local transcription state must persist")
    require("case .keepViewOncePhotos, .localVoiceTranscription:" in runtime, "local transcription must default OFF")
    require("Расшифровка голосовых" in settings_controller, "Client Premium switch missing")
    require("arguments.updateBool(.localVoiceTranscription, $0)" in settings_controller, "Client Premium switch action missing")
    require("localVoiceTranscription(snapshot.localVoiceTranscription)" in settings_controller, "Client Premium switch state missing")
    require(voice_node.count("AYU_LOCAL_VOICE_TRANSCRIPTION_v1") == 1, "voice overlay missing/duplicated")
    require("AyuRuntimeSettings.value(.localVoiceTranscription) || arguments.associatedData.isPremium" in voice_node, "Telegram-style transcribe button is not shown")
    require("AyuRuntimeSettings.value(.localVoiceTranscription) || context.sharedContext.immediateExperimentalUISettings.localTranscription" in voice_node, "local transcription path not selected")
    require("filter { $0.isComplete }" in voice_node, "voice download completion handling missing")
    require("request.requiresOnDeviceRecognition = true" in speech_node, "on-device-only speech setting missing")
    require("speechRecognizer.supportsOnDeviceRecognition" in speech_node, "speech on-device support check missing")

    print("=== Verify resend copies of locally deleted text / voice ===", flush=True)
    enqueue_source = (telegram / "submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift").read_text(encoding="utf-8")
    forward_ui = (telegram / "submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift").read_text(encoding="utf-8")
    require(enqueue_source.count("AYU_DELETED_FORWARD_COPY_v1") == 1, "deleted forward copy hook missing/duplicated")
    require(forward_ui.count("AYU_DELETED_FORWARD_UI_v1") == 1, "deleted forward UI guard missing/duplicated")
    require("if AyuRuntimeSettings.isDeleted(sourceId), let savedMessage = transaction.getMessage(sourceId)" in enqueue_source, "deleted forwards not converted to copies")
    require("Отправитель: " in enqueue_source and "sourceMessage.forwardInfo?.author" not in enqueue_source.split("AYU_DELETED_FORWARD_COPY_v1", 1)[1].split("if let sourceMessage = forwardedMessageToBeReuploaded", 1)[0], "deleted forward sender attribution invalid")
    require("copyResourceData(" in enqueue_source and "from: voice.resource.id, to: localResource.id, synchronous: true" in enqueue_source, "voice bytes are not locally reuploaded")
    require("mediaReference: copiedVoice" in enqueue_source, "copied voice not attached to outgoing message")
    require("correlationId: correlationId" in enqueue_source, "outgoing correlation id lost")
    require("AyuRuntimeSettings.isDeleted(message.id)" in forward_ui, "deleted voice UI warning missing")
    require("completedResourcePath(voice.resource) == nil" in forward_ui, "uncached deleted voice was not guarded")
    require("return self.context.account.postbox.mediaBox.completedResourcePath" in forward_ui, "voice guard bypassed")
    require("case let .forward(sourceId, threadId, _, requestedAttributes, correlationId):" in enqueue_source, "forward parameters discarded")

    print("=== Verify edit-history hooks ===", flush=True)
    runtime = (state_root / "AyuRuntimeSettings.swift").read_text(encoding="utf-8")
    history_store = (state_root / "AyuEditHistoryStore.swift").read_text(encoding="utf-8")
    request_edit = (telegram / "submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift").read_text(encoding="utf-8")
    context_menu = (telegram / "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift").read_text(encoding="utf-8")
    settings_controller = (peer_info_root / "AyuSettingsController.swift").read_text(encoding="utf-8")
    require("case trackEditedMessages" in runtime, "edit-history setting missing")
    require("public enum AyuEditHistoryStore" in history_store, "edit-history store missing")
    require("AyuEditHistoryStore.record" in state_utils, "remote edit-history hook missing")
    require(request_edit.count("AyuEditHistoryStore.record") >= 4, "outgoing edit-history hooks missing")
    require("История изменений" in context_menu, "edit-history context menu action missing")
    require("AyuEditHistoryStore.versions(for: message.id)" in context_menu, "edit-history context menu lookup missing")
    require("Сохранять историю изменений" in settings_controller, "edit-history settings switch missing")
    require("AyuEditHistoryStore.clearAll()" in settings_controller, "edit-history clear action missing")

    print("=== Verify profile field cache ===", flush=True)
    profile = (peer_info_root / "PeerInfoProfileItems.swift").read_text(encoding="utf-8")
    for needle in (
        "AYU_IOS_PROFILE_CACHE_v0_3",
        "user.phone ?? ayuCachedProfile.phone",
        "user.addressName ?? ayuCachedProfile.username",
        "ayuCachedProfile.note",
    ):
        require(needle in profile, f"profile cache hook missing: {needle}")

    cache_payload = (peer_info_root / "AyuProfileFieldCache.swift").read_text(encoding="utf-8")
    require("var phone: String? = nil" in cache_payload, "profile cache Codable defaults missing")
    require("var username: String? = nil" in cache_payload, "profile cache Codable username default missing")
    require("var note: String? = nil" in cache_payload, "profile cache Codable note default missing")
    require("String(peerId.toInt64())" in cache_payload, "profile cache uses an unsafe/internal PeerId key path")

    print("=== Verify unlimited pins runtime switch ===", flush=True)
    unlimited = (state_root / "AyuUnlimitedPins.swift").read_text(encoding="utf-8")
    toggle_pins = (telegram / "submodules/TelegramCore/Sources/TelegramEngine/Peers/TogglePeerChatPinned.swift").read_text(encoding="utf-8")
    reset_state = (state_root / "ResetState.swift").read_text(encoding="utf-8")
    holes = (state_root / "Holes.swift").read_text(encoding="utf-8")
    require("public static var isEnabled" in unlimited, "unlimited-pins persisted switch missing")
    require("trimToServerLimits" in unlimited, "unlimited-pins disable trim missing")
    require("if AyuUnlimitedPins.isEnabled" in toggle_pins, "pin limit is not runtime-gated")
    require("if AyuUnlimitedPins.isEnabled" in reset_state, "reset-state local pin merge is not runtime-gated")
    require("if AyuUnlimitedPins.isEnabled" in holes, "chat-list hole local pin merge is not runtime-gated")
    require("Безлимитные закрепы" in settings_controller, "unlimited-pins settings switch missing")
    require("AyuUnlimitedPins.setEnabled(value)" in settings_controller, "unlimited-pins settings action missing")
    require("AyuUnlimitedPins.trimToServerLimits" in settings_controller, "unlimited-pins disable cleanup missing")

    print("=== Verify client Premium ads + icons ===", flush=True)
    ads_settings = (state_root / "AyuAdsSettings.swift").read_text(encoding="utf-8")
    ad_messages = (telegram / "submodules/TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift").read_text(encoding="utf-8")
    theme_settings = (telegram / "submodules/SettingsUI/Sources/Themes/ThemeSettingsController.swift").read_text(encoding="utf-8")
    require("hideAdsSignal" in ads_settings, "reactive ad setting missing")
    require("unlockPremiumIcons" in ads_settings, "Premium icon setting missing")
    require("combineLatest(impl.state.get(), AyuAdsSettings.hideAdsSignal)" in ad_messages, "already-open ad contexts are not gated")
    require(ad_messages.count("AyuAdsSettings.hideAds") >= 4, "ad blocking hooks are incomplete")
    require(theme_settings.count("AyuAdsSettings.unlockPremiumIcons") >= 3, "Premium icon gates are not fully bypassed")
    require("Отключить рекламу" in settings_controller, "ad-block settings switch missing")
    require("Разблокировать Premium-иконки" in settings_controller, "Premium icon settings switch missing")
    require("AyuAdsSettings.setUnlockPremiumIcons(value)" in settings_controller, "Premium icon settings action missing")

    print("=== Verify all patch markers ===", flush=True)
    marker_files = (
        "submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift",
        "submodules/TelegramCore/Sources/State/ManagedLocalInputActivities.swift",
        "submodules/TelegramCore/Sources/State/SynchronizePeerReadState.swift",
        "submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift",
        "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift",
        "submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift",
        "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift",
        "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/ChatMessageDateAndStatusNode.swift",
        "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoSettingsItems.swift",
        "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoData.swift",
    )
    for relative in marker_files:
        text = (telegram / relative).read_text(encoding="utf-8")
        require("AYU_IOS_PATCH_v0_3" in text, f"patch marker missing in {relative}")
        print(f"OK: {relative}")

    edit_marker_files = (
        "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift",
        "submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift",
        "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift",
    )
    for relative in edit_marker_files:
        text = (telegram / relative).read_text(encoding="utf-8")
        require("AYU_IOS_EDIT_HISTORY_v1" in text, f"edit-history patch marker missing in {relative}")
        print(f"OK edit history: {relative}")

    require("AYU_UNLIMITED_PINS_v2" in toggle_pins, "unlimited-pins v2 marker missing")
    require("AYU_CLIENT_PREMIUM_v2" in ad_messages, "client-Premium ad marker missing")
    require("AYU_CLIENT_PREMIUM_v2" in theme_settings, "client-Premium icon marker missing")
    require("AYU_CLIENT_PREMIUM_v2" in settings_controller, "client-Premium settings marker missing")

    require("func ayuSettingsController(context: AccountContext)" in settings_controller, "Ayu settings controller entrypoint missing")
    ghost_last_seen = (state_root / "AyuGhostLastSeen.swift").read_text(encoding="utf-8")
    require("public enum AyuGhostLastSeen" in ghost_last_seen, "Ghost last-seen runtime missing")

    print("=== VERIFY SUCCESS ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"=== VERIFY FAILURE ===\n{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
