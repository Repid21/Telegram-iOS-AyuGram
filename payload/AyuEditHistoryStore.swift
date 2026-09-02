import Foundation
import Postbox
import SwiftSignalKit

public struct AyuMessageEditVersion: Codable, Equatable {
    public let text: String
    public let validUntil: Int32

    public init(text: String, validUntil: Int32) {
        self.text = text
        self.validUntil = validUntil
    }
}

private struct AyuEditHistoryState: Codable {
    var messages: [String: [AyuMessageEditVersion]]
    var order: [String]

    init(messages: [String: [AyuMessageEditVersion]] = [:], order: [String] = []) {
        self.messages = messages
        self.order = order
    }
}

/// Local edit history for Telegram messages.
/// Each stored entry is the text that existed immediately before an edit and
/// the moment when that version stopped being current.
public enum AyuEditHistoryStore {
    private static let storageKey = "com.nomadvorga.telegram.ayu.v03.editHistory"
    private static let maxMessages = 5_000
    private static let maxVersionsPerMessage = 50

    private static func messageKey(_ id: MessageId) -> String {
        return "\(id.peerId.toInt64()):\(id.namespace):\(id.id)"
    }

    private static func loadState() -> AyuEditHistoryState {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let value = try? JSONDecoder().decode(AyuEditHistoryState.self, from: data) else {
            return AyuEditHistoryState()
        }
        return value
    }

    private static let state = Atomic<AyuEditHistoryState>(value: loadState())

    private static func persist(_ value: AyuEditHistoryState) {
        if let data = try? JSONEncoder().encode(value) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    public static func record(messageId: MessageId, previousText: String, newText: String, validUntil: Int32) {
        guard AyuRuntimeSettings.trackEditedMessages, previousText != newText else {
            return
        }

        let key = messageKey(messageId)
        var updatedState: AyuEditHistoryState?
        _ = state.modify { current in
            var current = current
            var versions = current.messages[key] ?? []

            // The same server edit can pass through both the direct edit response
            // and AccountStateManager. Do not store it twice.
            if versions.last?.text == previousText && versions.last?.validUntil == validUntil {
                return current
            }
            if versions.last?.text == previousText && versions.last?.validUntil != validUntil {
                versions[versions.count - 1] = AyuMessageEditVersion(text: previousText, validUntil: validUntil)
            } else {
                versions.append(AyuMessageEditVersion(text: previousText, validUntil: validUntil))
            }

            if versions.count > maxVersionsPerMessage {
                versions.removeFirst(versions.count - maxVersionsPerMessage)
            }
            current.messages[key] = versions

            current.order.removeAll(where: { $0 == key })
            current.order.append(key)
            if current.order.count > maxMessages {
                let overflow = current.order.count - maxMessages
                let removed = Array(current.order.prefix(overflow))
                current.order.removeFirst(overflow)
                for removedKey in removed {
                    current.messages.removeValue(forKey: removedKey)
                }
            }

            updatedState = current
            return current
        }

        if let updatedState {
            persist(updatedState)
        }
    }

    public static func versions(for messageId: MessageId) -> [AyuMessageEditVersion] {
        let key = messageKey(messageId)
        return state.with { value in
            return value.messages[key] ?? []
        }
    }

    public static func clearAll() {
        _ = state.modify { _ in
            return AyuEditHistoryState()
        }
        UserDefaults.standard.removeObject(forKey: storageKey)
    }

    public static func formattedTimestamp(_ timestamp: Int32) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale.current
        formatter.dateFormat = "dd.MM.yy 'в' HH:mm:ss"
        return formatter.string(from: Date(timeIntervalSince1970: TimeInterval(timestamp)))
    }
}
