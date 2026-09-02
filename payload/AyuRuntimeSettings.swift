import Foundation
import Postbox
import SwiftSignalKit

public enum AyuRuntimeOption: Int32, CaseIterable {
    case master = 0
    case hideReadMessages = 1
    case hideReadStories = 2
    case hideOnline = 3
    case hideTyping = 4
    case automaticOffline = 5
    case onlinePulseOnSend = 6
    case keepDeletedMessages = 7
    case showDeletedMarker = 8
    case trackEditedMessages = 9
}

public enum AyuDeletedMarkerStyle: Int32, CaseIterable {
    case trash = 0
    case text = 1
    case cross = 2
    case compact = 3
}

public enum AyuDeletedMarkerColor: Int32, CaseIterable {
    case red = 0
    case orange = 1
    case gray = 2
    case purple = 3
}

public struct AyuRuntimeSnapshot: Equatable {
    public var master: Bool
    public var hideReadMessages: Bool
    public var hideReadStories: Bool
    public var hideOnline: Bool
    public var hideTyping: Bool
    public var automaticOffline: Bool
    public var onlinePulseOnSend: Bool
    public var keepDeletedMessages: Bool
    public var showDeletedMarker: Bool
    public var trackEditedMessages: Bool
    public var deletedMarkerStyle: Int32
    public var deletedMarkerColor: Int32
}

private struct AyuDeletedState {
    var globalIds: Set<Int32>
    var fullIds: Set<String>
}

/// Runtime state for the iOS Ayu port.
/// Hot paths only touch in-memory Atomics. UserDefaults is used for persistence,
/// never as a per-message/per-request lookup.
public enum AyuRuntimeSettings {
    private static let keyPrefix = "com.nomadvorga.telegram.ayu.v03."
    private static let legacyKeyPrefix = "com.nomadvorga.telegram.ayu.v02."
    private static let deletedGlobalKey = keyPrefix + "deleted.global"
    private static let deletedFullKey = keyPrefix + "deleted.full"
    private static let deletedMarkerStyleKey = keyPrefix + "deleted.markerStyle"
    private static let deletedMarkerColorKey = keyPrefix + "deleted.markerColor"
    private static let maxDeletedMarkers = 20_000

    private static func key(_ option: AyuRuntimeOption) -> String {
        switch option {
        case .master:
            return keyPrefix + "master"
        case .hideReadMessages:
            return keyPrefix + "hideReadMessages"
        case .hideReadStories:
            return keyPrefix + "hideReadStories"
        case .hideOnline:
            return keyPrefix + "hideOnline"
        case .hideTyping:
            return keyPrefix + "hideTyping"
        case .automaticOffline:
            return keyPrefix + "automaticOffline"
        case .onlinePulseOnSend:
            return keyPrefix + "onlinePulseOnSend"
        case .keepDeletedMessages:
            return keyPrefix + "keepDeletedMessages"
        case .showDeletedMarker:
            return keyPrefix + "showDeletedMarker"
        case .trackEditedMessages:
            return keyPrefix + "trackEditedMessages"
        }
    }

    private static func defaultValue(_ option: AyuRuntimeOption) -> Bool {
        switch option {
        case .master:
            return false
        case .hideReadMessages, .hideReadStories, .hideOnline, .hideTyping, .automaticOffline, .onlinePulseOnSend, .keepDeletedMessages, .showDeletedMarker, .trackEditedMessages:
            return true
        }
    }

    private static func storedValue(_ option: AyuRuntimeOption, defaults: UserDefaults) -> Bool {
        let optionKey = key(option)
        if defaults.object(forKey: optionKey) != nil {
            return defaults.bool(forKey: optionKey)
        }
        // Migrate v0.2 privacy toggles without changing the user's current Ghost setup.
        switch option {
        case .master, .hideReadMessages, .hideReadStories, .hideOnline, .hideTyping, .automaticOffline:
            let suffix = optionKey.replacingOccurrences(of: keyPrefix, with: "")
            let legacyKey = legacyKeyPrefix + suffix
            if defaults.object(forKey: legacyKey) != nil {
                return defaults.bool(forKey: legacyKey)
            }
        case .onlinePulseOnSend, .keepDeletedMessages, .showDeletedMarker, .trackEditedMessages:
            break
        }
        return defaultValue(option)
    }

    private static func loadSnapshot() -> AyuRuntimeSnapshot {
        let defaults = UserDefaults.standard
        let style: Int32
        if defaults.object(forKey: deletedMarkerStyleKey) == nil {
            style = AyuDeletedMarkerStyle.trash.rawValue
        } else {
            style = Int32(defaults.integer(forKey: deletedMarkerStyleKey))
        }
        let color: Int32
        if defaults.object(forKey: deletedMarkerColorKey) == nil {
            color = AyuDeletedMarkerColor.red.rawValue
        } else {
            color = Int32(defaults.integer(forKey: deletedMarkerColorKey))
        }
        return AyuRuntimeSnapshot(
            master: storedValue(.master, defaults: defaults),
            hideReadMessages: storedValue(.hideReadMessages, defaults: defaults),
            hideReadStories: storedValue(.hideReadStories, defaults: defaults),
            hideOnline: storedValue(.hideOnline, defaults: defaults),
            hideTyping: storedValue(.hideTyping, defaults: defaults),
            automaticOffline: storedValue(.automaticOffline, defaults: defaults),
            onlinePulseOnSend: storedValue(.onlinePulseOnSend, defaults: defaults),
            keepDeletedMessages: storedValue(.keepDeletedMessages, defaults: defaults),
            showDeletedMarker: storedValue(.showDeletedMarker, defaults: defaults),
            trackEditedMessages: storedValue(.trackEditedMessages, defaults: defaults),
            deletedMarkerStyle: style,
            deletedMarkerColor: color
        )
    }

    private static func loadDeletedState() -> AyuDeletedState {
        let defaults = UserDefaults.standard
        let rawGlobal = defaults.array(forKey: deletedGlobalKey) as? [Int] ?? []
        let globalIds = Set(rawGlobal.compactMap { Int32(exactly: $0) })
        let fullIds = Set(defaults.stringArray(forKey: deletedFullKey) ?? [])
        return AyuDeletedState(globalIds: globalIds, fullIds: fullIds)
    }

    private static let state = Atomic<AyuRuntimeSnapshot>(value: loadSnapshot())
    private static let deletedState = Atomic<AyuDeletedState>(value: loadDeletedState())

    public static var snapshot: AyuRuntimeSnapshot {
        return state.with { $0 }
    }

    public static func value(_ option: AyuRuntimeOption) -> Bool {
        let current = snapshot
        switch option {
        case .master:
            return current.master
        case .hideReadMessages:
            return current.hideReadMessages
        case .hideReadStories:
            return current.hideReadStories
        case .hideOnline:
            return current.hideOnline
        case .hideTyping:
            return current.hideTyping
        case .automaticOffline:
            return current.automaticOffline
        case .onlinePulseOnSend:
            return current.onlinePulseOnSend
        case .keepDeletedMessages:
            return current.keepDeletedMessages
        case .showDeletedMarker:
            return current.showDeletedMarker
        case .trackEditedMessages:
            return current.trackEditedMessages
        }
    }

    public static func set(_ option: AyuRuntimeOption, value: Bool) {
        UserDefaults.standard.set(value, forKey: key(option))
        _ = state.modify { current in
            var current = current
            switch option {
            case .master:
                current.master = value
            case .hideReadMessages:
                current.hideReadMessages = value
            case .hideReadStories:
                current.hideReadStories = value
            case .hideOnline:
                current.hideOnline = value
            case .hideTyping:
                current.hideTyping = value
            case .automaticOffline:
                current.automaticOffline = value
            case .onlinePulseOnSend:
                current.onlinePulseOnSend = value
            case .keepDeletedMessages:
                current.keepDeletedMessages = value
            case .showDeletedMarker:
                current.showDeletedMarker = value
            case .trackEditedMessages:
                current.trackEditedMessages = value
            }
            return current
        }
    }

    public static func setDeletedMarkerStyle(_ value: Int32) {
        let normalized = AyuDeletedMarkerStyle(rawValue: value)?.rawValue ?? AyuDeletedMarkerStyle.trash.rawValue
        UserDefaults.standard.set(Int(normalized), forKey: deletedMarkerStyleKey)
        _ = state.modify { current in
            var current = current
            current.deletedMarkerStyle = normalized
            return current
        }
    }

    public static func setDeletedMarkerColor(_ value: Int32) {
        let normalized = AyuDeletedMarkerColor(rawValue: value)?.rawValue ?? AyuDeletedMarkerColor.red.rawValue
        UserDefaults.standard.set(Int(normalized), forKey: deletedMarkerColorKey)
        _ = state.modify { current in
            var current = current
            current.deletedMarkerColor = normalized
            return current
        }
    }

    public static var suppressReadMessages: Bool {
        return state.with { $0.master && $0.hideReadMessages }
    }

    public static var suppressStoryViews: Bool {
        return state.with { $0.master && $0.hideReadStories }
    }

    public static var suppressOnlineStatus: Bool {
        return state.with { $0.master && $0.hideOnline }
    }

    public static var suppressTypingActivities: Bool {
        return state.with { $0.master && $0.hideTyping }
    }

    public static var shouldSendAutomaticOffline: Bool {
        return state.with { $0.master && $0.hideOnline && $0.automaticOffline }
    }

    public static var shouldPulseOnlineOnSend: Bool {
        return state.with { $0.master && $0.hideOnline && $0.onlinePulseOnSend }
    }

    public static var keepDeletedMessages: Bool {
        return state.with { $0.keepDeletedMessages }
    }

    public static var showDeletedMarker: Bool {
        return state.with { $0.keepDeletedMessages && $0.showDeletedMarker }
    }

    public static var trackEditedMessages: Bool {
        return state.with { $0.trackEditedMessages }
    }

    private static func fullKey(_ id: MessageId) -> String {
        return "\(id.peerId.namespace):\(id.peerId.id._internalGetInt64Value()):\(id.namespace):\(id.id)"
    }

    private static func persistDeletedState(_ value: AyuDeletedState) {
        let defaults = UserDefaults.standard
        defaults.set(value.globalIds.map(Int.init), forKey: deletedGlobalKey)
        defaults.set(Array(value.fullIds), forKey: deletedFullKey)
    }

    public static func markDeletedGlobalIds(_ ids: [Int32]) {
        guard !ids.isEmpty else {
            return
        }
        var updated: AyuDeletedState?
        _ = deletedState.modify { current in
            var current = current
            for id in ids {
                current.globalIds.insert(id)
            }
            if current.globalIds.count > maxDeletedMarkers {
                current.globalIds = Set(current.globalIds.prefix(maxDeletedMarkers))
            }
            updated = current
            return current
        }
        if let updated {
            persistDeletedState(updated)
        }
    }

    public static func markDeletedMessageIds(_ ids: [MessageId]) {
        guard !ids.isEmpty else {
            return
        }
        var updated: AyuDeletedState?
        _ = deletedState.modify { current in
            var current = current
            for id in ids {
                current.fullIds.insert(fullKey(id))
            }
            if current.fullIds.count > maxDeletedMarkers {
                current.fullIds = Set(current.fullIds.prefix(maxDeletedMarkers))
            }
            updated = current
            return current
        }
        if let updated {
            persistDeletedState(updated)
        }
    }

    public static func clearDeletedMarkers() {
        _ = deletedState.modify { _ in
            return AyuDeletedState(globalIds: Set(), fullIds: Set())
        }
        UserDefaults.standard.removeObject(forKey: deletedGlobalKey)
        UserDefaults.standard.removeObject(forKey: deletedFullKey)
    }

    public static func isDeleted(_ id: MessageId) -> Bool {
        return deletedState.with { current in
            if current.fullIds.contains(fullKey(id)) {
                return true
            }
            if id.namespace == Namespaces.Message.Cloud && id.peerId.namespace != Namespaces.Peer.CloudChannel {
                return current.globalIds.contains(id.id)
            }
            return false
        }
    }

    public static var deletedMarkerPrefix: String {
        switch AyuDeletedMarkerStyle(rawValue: state.with({ $0.deletedMarkerStyle })) ?? .trash {
        case .trash:
            return "🗑"
        case .text:
            return "Удалено"
        case .cross:
            return "✕"
        case .compact:
            return "DEL"
        }
    }

    public static var deletedMarkerStyleTitle: String {
        switch AyuDeletedMarkerStyle(rawValue: state.with({ $0.deletedMarkerStyle })) ?? .trash {
        case .trash:
            return "🗑 Значок"
        case .text:
            return "Удалено"
        case .cross:
            return "✕ Крест"
        case .compact:
            return "DEL"
        }
    }

    public static var deletedMarkerColorTitle: String {
        switch AyuDeletedMarkerColor(rawValue: state.with({ $0.deletedMarkerColor })) ?? .red {
        case .red:
            return "Красный"
        case .orange:
            return "Оранжевый"
        case .gray:
            return "Серый"
        case .purple:
            return "Фиолетовый"
        }
    }

    public static func decorateTimestamp(_ text: String, messageId: MessageId) -> String {
        guard showDeletedMarker && isDeleted(messageId) else {
            return text
        }
        return "\(deletedMarkerPrefix) \(text)"
    }

    public static func isDeletedTimestampText(_ text: String) -> Bool {
        guard showDeletedMarker else {
            return false
        }
        return text.hasPrefix(deletedMarkerPrefix + " ")
    }
}
