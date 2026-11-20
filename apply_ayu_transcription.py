#!/usr/bin/env python3
"""Use Telegram's native voice-to-text button with optional on-device recognition.

Run AFTER apply_ayu_view_once_photos.py so the final Client Premium page is present.
No server-side Premium emulation, Telegram transcription API, or remote audio service.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARK = "AYU_LOCAL_VOICE_TRANSCRIPTION_v1"
SETTINGS_PATH = "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/AyuSettingsController.swift"
VOICE_PATH = "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveFileNode/Sources/ChatMessageInteractiveFileNode.swift"
SPEECH_PATH = "submodules/Media/LocalAudioTranscription/Sources/LocalAudioTranscription.swift"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return source.replace(old, new, 1)


def patch_settings(source: str) -> str:
    source = replace_once(
        source, "    case premiumIcons(Bool)\n",
        "    case premiumIcons(Bool)\n    case localVoiceTranscription(Bool)\n",
        "settings-option",
    )
    source = replace_once(
        source, "        case .premiumHeader, .hideAds, .premiumIcons:",
        "        case .premiumHeader, .hideAds, .premiumIcons, .localVoiceTranscription:",
        "settings-section",
    )
    source = replace_once(
        source, "        case .premiumIcons: return 52\n",
        "        case .premiumIcons: return 52\n        case .localVoiceTranscription: return 53\n",
        "settings-id",
    )
    source = replace_once(
        source,
        '        case .premiumHeader:\n            return ItemListSectionHeaderItem(presentationData: presentationData, text: "КЛИЕНТСКИЙ PREMIUM", sectionId: self.section)',
        '''        // AYU_LOCAL_VOICE_TRANSCRIPTION_v1: user-controlled free, local voice-to-text.
        case let .localVoiceTranscription(value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                systemStyle: .glass,
                title: "Расшифровка голосовых",
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: { arguments.updateBool(.localVoiceTranscription, $0) }
            )
        case .premiumHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "КЛИЕНТСКИЙ PREMIUM", sectionId: self.section)''',
        "settings-switch",
    )
    source = replace_once(
        source,
        "            .premiumIcons(AyuAdsSettings.unlockPremiumIcons)\n",
        "            .premiumIcons(AyuAdsSettings.unlockPremiumIcons),\n"
        "            .localVoiceTranscription(snapshot.localVoiceTranscription)\n",
        "settings-premium-items",
    )
    return source


def patch_voice(source: str) -> str:
    source = replace_once(
        source,
        "    private func transcribe() {\n",
        "    // AYU_LOCAL_VOICE_TRANSCRIPTION_v1: reuse Telegram's spinner, button and text layout.\n"
        "    private func transcribe() {\n",
        "voice-marker",
    )
    source = replace_once(
        source,
        "if transcriptionText == nil && !arguments.associatedData.alwaysDisplayTranscribeButton.providedByGroupBoost {",
        "if transcriptionText == nil && !AyuRuntimeSettings.value(.localVoiceTranscription) && !arguments.associatedData.alwaysDisplayTranscribeButton.providedByGroupBoost {",
        "voice-premium-paywall",
    )
    source = replace_once(
        source,
        "if context.sharedContext.immediateExperimentalUISettings.localTranscription {",
        "if AyuRuntimeSettings.value(.localVoiceTranscription) || context.sharedContext.immediateExperimentalUISettings.localTranscription {",
        "voice-local-route",
    )
    source = replace_once(
        source,
        "                    let appLocale = presentationData.strings.baseLanguageCode\n",
        """                    let appLocale = presentationData.strings.baseLanguageCode
                    // Voice may not have been downloaded yet. Start Telegram's own
                    // existing fetch and wait for the complete local file.
                    if let fetch = self.fetchControls.with({ $0?.fetch }) {
                        fetch(true)
                    }
""",
        "voice-start-fetch",
    )
    source = replace_once(
        source,
        """                        return context.engine.resources.data(id: EngineMediaResource.Id(file.resource.id))
                        |> take(1)
                        |> mapToSignal { data -> Signal<String?, NoError> in
                            if !data.isComplete {
                                return .single(nil)
                            }
                            return .single(data.path)
                        }""",
        """                        return context.engine.resources.data(id: EngineMediaResource.Id(file.resource.id))
                        |> filter { $0.isComplete }
                        |> take(1)
                        |> map { data -> String? in
                            return data.path
                        }""",
        "voice-wait-download",
    )
    source = replace_once(
        source,
        "if arguments.associatedData.isPremium || arguments.associatedData.alwaysDisplayTranscribeButton.providedByGroupBoost {",
        "if AyuRuntimeSettings.value(.localVoiceTranscription) || arguments.associatedData.isPremium || arguments.associatedData.alwaysDisplayTranscribeButton.providedByGroupBoost {",
        "voice-button-visibility",
    )
    source = replace_once(
        source,
        "if transcribedText == nil, let cooldownUntilTime = arguments.associatedData.audioTranscriptionTrial.cooldownUntilTime, cooldownUntilTime > currentTime {",
        "if !AyuRuntimeSettings.value(.localVoiceTranscription), transcribedText == nil, let cooldownUntilTime = arguments.associatedData.audioTranscriptionTrial.cooldownUntilTime, cooldownUntilTime > currentTime {",
        "voice-no-trial-lock",
    )
    return source


def patch_speech(source: str) -> str:
    source = replace_once(
        source,
        '''                            if locale == "en-US" {
                                speechRecognizer.supportsOnDeviceRecognition = true
                            } else {
                                speechRecognizer.supportsOnDeviceRecognition = false
                            }
                            speechRecognizer.supportsOnDeviceRecognition = true''',
        '''                            // AYU_LOCAL_VOICE_TRANSCRIPTION_v1: never send voice
                            // to Apple's server; require on-device language support.
                            guard speechRecognizer.supportsOnDeviceRecognition else {
                                subscriber.putNext(nil)
                                subscriber.putCompletion()
                                return
                            }''',
        "speech-on-device-capability",
    )
    source = replace_once(
        source,
        "                        request.requiresOnDeviceRecognition = speechRecognizer.supportsOnDeviceRecognition",
        "                        request.requiresOnDeviceRecognition = true",
        "speech-require-offline",
    )
    source = replace_once(
        source,
        '''    if !locales.contains(Locale.current.identifier) {
        locales.append(Locale.current.identifier)
    }''',
        '''    let preferredLocale = appLocale == "ru" ? "ru-RU" : (appLocale == "en" ? "en-US" : appLocale)
    if !preferredLocale.isEmpty && !locales.contains(preferredLocale) {
        locales.append(preferredLocale)
    }
    if !locales.contains(Locale.current.identifier) {
        locales.append(Locale.current.identifier)
    }''',
        "speech-app-language",
    )
    source = replace_once(
        source,
        "                                confidence /= Float(result.bestTranscription.segments.count)",
        "                                confidence /= Float(max(1, result.bestTranscription.segments.count))",
        "speech-empty-segments",
    )
    return source


def apply_file(root: Path, relative: str, patcher) -> None:
    target = root / relative
    if not target.is_file():
        raise RuntimeError(f"Missing pinned Telegram source: {target}")
    original = target.read_text(encoding="utf-8")
    if MARK in original:
        if original.count(MARK) != 1:
            raise RuntimeError(f"Duplicate {MARK} in {relative}")
        print(f"[ayu-transcribe] already patched: {relative}")
        return
    updated = patcher(original)
    if updated.count(MARK) != 1:
        raise RuntimeError(f"Expected one {MARK} in {relative}")
    target.write_text(updated, encoding="utf-8")
    print(f"[ayu-transcribe] patched: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("telegram_repo", type=Path)
    args = parser.parse_args()
    root = args.telegram_repo.resolve()
    apply_file(root, SETTINGS_PATH, patch_settings)
    apply_file(root, VOICE_PATH, patch_voice)
    apply_file(root, SPEECH_PATH, patch_speech)


if __name__ == "__main__":
    main()
