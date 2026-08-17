import Foundation
import SwiftSignalKit

public enum AyuRuntimeOption: Int32, CaseIterable {
    case master = 0
    case hideReadMessages = 1
    case hideReadStories = 2
    case hideOnline = 3
    case hideTyping = 4
    case automaticOffline = 5
}

public struct AyuRuntimeSnapshot: Equatable {
    public var master: Bool
    public var hideReadMessages: Bool
    public var hideReadStories: Bool
    public var hideOnline: Bool
    public var hideTyping: Bool
    public var automaticOffline: Bool
}

/// Runtime privacy state for the iOS Ayu port.
///
/// IMPORTANT FOR PERFORMANCE:
/// - UserDefaults is read only once when the process initializes.
/// - Network/render hot paths read only this Atomic in-memory snapshot.
/// - No polling, no extra timers, no background loop is introduced here.
public enum AyuRuntimeSettings {
    private static let keyPrefix = "com.nomadvorga.telegram.ayu.v02."

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
        }
    }

    private static func defaultValue(_ option: AyuRuntimeOption) -> Bool {
        switch option {
        case .master:
            // Stability-first: a fresh install behaves exactly like stock Telegram
            // until Ghost Mode is explicitly enabled.
            return false
        case .hideReadMessages, .hideReadStories, .hideOnline, .hideTyping, .automaticOffline:
            return true
        }
    }

    private static func storedValue(_ option: AyuRuntimeOption, defaults: UserDefaults) -> Bool {
        let optionKey = key(option)
        if defaults.object(forKey: optionKey) == nil {
            return defaultValue(option)
        }
        return defaults.bool(forKey: optionKey)
    }

    private static func loadSnapshot() -> AyuRuntimeSnapshot {
        let defaults = UserDefaults.standard
        return AyuRuntimeSnapshot(
            master: storedValue(.master, defaults: defaults),
            hideReadMessages: storedValue(.hideReadMessages, defaults: defaults),
            hideReadStories: storedValue(.hideReadStories, defaults: defaults),
            hideOnline: storedValue(.hideOnline, defaults: defaults),
            hideTyping: storedValue(.hideTyping, defaults: defaults),
            automaticOffline: storedValue(.automaticOffline, defaults: defaults)
        )
    }

    private static let state = Atomic<AyuRuntimeSnapshot>(value: loadSnapshot())

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
            }
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
}
