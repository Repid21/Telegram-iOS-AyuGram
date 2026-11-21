#!/usr/bin/env python3
"""Allow recipients to receive copies of locally preserved deleted texts / voices.

Telegram cannot actually forward a deleted source message: the server rejects
the original ID, creating a failed bubble visible only to the sender.

Replace the outgoing forward request at enqueue time with a genuinely new
message. Attribute the author in *plain text*, not a forged Telegram server
forward header. For cached voice notes, copy bytes into a new local resource
and reupload them. Non-downloaded voices are rejected in the chat forward UI
with an actionable explanation rather than silently sending a placeholder.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARK = "AYU_DELETED_FORWARD_COPY_v1"
UI_MARK = "AYU_DELETED_FORWARD_UI_v1"
ENQUEUE = "submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift"
UI = "submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift"

ENQUEUE_ANCHOR = """            case let .forward(sourceId, threadId, _, _, _):
                if let sourceMessage = forwardedMessageToBeReuploaded(transaction: transaction, id: sourceId) {
"""

ENQUEUE_REPLACEMENT = r'''            case let .forward(sourceId, threadId, _, requestedAttributes, correlationId):
                // AYU_DELETED_FORWARD_COPY_v1: Telegram's forwardMessages API cannot
                // resolve a deleted source. Resend local content with an attribution
                // note, so the RECIPIENT sees it as a real new message instead of
                // a local-only failed forward bubble.
                if AyuRuntimeSettings.isDeleted(sourceId), let savedMessage = transaction.getMessage(sourceId) {
                    let hideNames = requestedAttributes.contains(where: {
                        ($0 as? ForwardOptionsMessageAttribute)?.hideNames == true
                    })
                    let hideCaption = requestedAttributes.contains(where: {
                        ($0 as? ForwardOptionsMessageAttribute)?.hideCaptions == true
                    })
                    let originalSender = savedMessage.forwardInfo?.author ?? savedMessage.author ?? savedMessage.peers[savedMessage.id.peerId]
                    let senderName: String
                    if let originalSender {
                        var name = originalSender.debugDisplayTitle
                        if let username = originalSender.addressName, !username.isEmpty {
                            name += " (@\(username))"
                        }
                        senderName = name.isEmpty ? "Неизвестен" : name
                    } else if let signature = savedMessage.forwardInfo?.authorSignature, !signature.isEmpty {
                        senderName = signature
                    } else {
                        senderName = "Неизвестен"
                    }

                    var copyText = "↪ Копия удалённого сообщения"
                    if !hideNames {
                        copyText += "\nОтправитель: \(senderName)"
                    }
                    if !hideCaption && !savedMessage.text.isEmpty {
                        copyText += "\n\n\(savedMessage.text)"
                    }

                    var copiedVoice: AnyMediaReference?
                    if let voice = savedMessage.media.first(where: {
                        ($0 as? TelegramMediaFile)?.isVoice == true
                    }) as? TelegramMediaFile {
                        // Voice bytes must exist on this device. A cloud document
                        // reference from a DELETED message is not a valid fallback.
                        if account.postbox.mediaBox.completedResourcePath(voice.resource) != nil {
                            let newId = Int64.random(in: Int64.min ... Int64.max)
                            let localResource = LocalFileMediaResource(fileId: newId, size: voice.size)
                            account.postbox.mediaBox.copyResourceData(
                                from: voice.resource.id, to: localResource.id, synchronous: true
                            )
                            let localVoice = TelegramMediaFile(
                                fileId: MediaId(namespace: Namespaces.Media.LocalFile, id: newId),
                                partialReference: nil,
                                resource: localResource,
                                previewRepresentations: [],
                                videoThumbnails: [],
                                immediateThumbnailData: nil,
                                mimeType: voice.mimeType,
                                size: voice.size,
                                attributes: voice.attributes,
                                alternativeRepresentations: []
                            )
                            copiedVoice = .standalone(media: localVoice)
                        } else {
                            // Leave the original forward as a fallback for callers
                            // outside chat UI; the chat forward dialog checks this
                            // condition BEFORE showing the recipient picker.
                            updatedMessages.append((transformedMedia, updatedMessage))
                            continue outer
                        }
                    } else if !savedMessage.media.isEmpty {
                        // No text-only fake replacement for unsupported media.
                        updatedMessages.append((transformedMedia, updatedMessage))
                        continue outer
                    }

                    let outgoingAttributes = requestedAttributes.filter {
                        !($0 is ForwardOptionsMessageAttribute)
                    }
                    updatedMessages.append((false, .message(
                        text: copyText,
                        attributes: outgoingAttributes,
                        inlineStickers: [:],
                        mediaReference: copiedVoice,
                        threadId: threadId,
                        replyToMessageId: threadId.flatMap {
                            EngineMessageReplySubject(
                                messageId: MessageId(
                                    peerId: peerId,
                                    namespace: Namespaces.Message.Cloud,
                                    id: Int32(clamping: $0)
                                ),
                                quote: nil,
                                innerSubject: nil
                            )
                        },
                        replyToStoryId: nil,
                        localGroupingKey: nil,
                        correlationId: correlationId,
                        bubbleUpEmojiOrStickersets: []
                    )))
                    continue outer
                }
                if let sourceMessage = forwardedMessageToBeReuploaded(transaction: transaction, id: sourceId) {
'''

UI_ANCHOR = """    func forwardMessages(messages: [EngineRawMessage], options: ChatInterfaceForwardOptionsState? = nil, resetCurrent: Bool) {
        let _ = self.presentVoiceMessageDiscardAlert(action: {
"""

UI_REPLACEMENT = '''    func forwardMessages(messages: [EngineRawMessage], options: ChatInterfaceForwardOptionsState? = nil, resetCurrent: Bool) {
        // AYU_DELETED_FORWARD_UI_v1: never enqueue an unforwardable deleted
        // voice when its audio is not already fully cached on this device.
        let missingDeletedVoice = messages.contains { message in
            guard AyuRuntimeSettings.isDeleted(message.id),
                  let voice = message.media.first(where: {
                      ($0 as? TelegramMediaFile)?.isVoice == true
                  }) as? TelegramMediaFile else {
                return false
            }
            return self.context.account.postbox.mediaBox.completedResourcePath(voice.resource) == nil
        }
        if missingDeletedVoice {
            let alert = textAlertController(
                context: self.context,
                updatedPresentationData: self.updatedPresentationData,
                title: "Голосовое не загружено",
                text: "Сначала открой удалённое голосовое и дождись полной загрузки аудио. Затем повтори пересылку. Telegram уже удалил оригинал, поэтому AyuGram может отправить только сохранённую на устройстве копию.",
                actions: [
                    TextAlertAction(type: .defaultAction, title: self.presentationData.strings.Common_OK, action: {})
                ]
            )
            self.present(alert, in: .window(.root))
            return
        }
        let _ = self.presentVoiceMessageDiscardAlert(action: {
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def apply(root: Path, rel: str, marker: str, original: str, replacement: str) -> None:
    target = root / rel
    if not target.is_file():
        raise RuntimeError(f"Missing pinned Telegram source: {target}")
    source = target.read_text(encoding="utf-8")
    if marker in source:
        if source.count(marker) != 1:
            raise RuntimeError(f"Duplicated marker: {marker}")
        print(f"[ayu-deleted-forward] already patched {rel}")
        return
    updated = replace_once(source, original, replacement, rel)
    if updated.count(marker) != 1:
        raise RuntimeError(f"Missing marker after patching {rel}")
    target.write_text(updated, encoding="utf-8")
    print(f"[ayu-deleted-forward] patched {rel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("telegram_repo", type=Path)
    args = parser.parse_args()
    root = args.telegram_repo.resolve()
    apply(root, ENQUEUE, MARK, ENQUEUE_ANCHOR, ENQUEUE_REPLACEMENT)
    apply(root, UI, UI_MARK, UI_ANCHOR, UI_REPLACEMENT)


if __name__ == "__main__":
    main()
