import Foundation
import Postbox
import SwiftSignalKit

/// Local unlimited pins for AyuGram iOS.
/// Telegram's server still enforces the account pin limit; only the first
/// server-visible pins are synchronized. Overflow pins stay on this device.
public enum AyuUnlimitedPins {
    private static let enabledKey = "com.nomadvorga.telegram.ayu.v03.unlimitedPins"

    private static func loadEnabled() -> Bool {
        let defaults = UserDefaults.standard
        if defaults.object(forKey: enabledKey) == nil {
            // Preserve the behavior of builds where unlimited pins were always on.
            return true
        }
        return defaults.bool(forKey: enabledKey)
    }

    private static let enabledState = Atomic<Bool>(value: loadEnabled())

    public static var isEnabled: Bool {
        return enabledState.with { $0 }
    }

    public static func setEnabled(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: enabledKey)
        _ = enabledState.modify { _ in value }
    }

    public static func serverLimit(transaction: Transaction, accountPeerId: PeerId, groupId: PeerGroupId) -> Int {
        let isPremium = transaction.getPeer(accountPeerId)?.isPremium ?? false
        let appConfiguration = transaction.getPreferencesEntry(key: PreferencesKeys.appConfiguration)?.get(AppConfiguration.self) ?? .defaultValue
        let limits = UserLimitsConfiguration(appConfiguration: appConfiguration, isPremium: isPremium)
        if case .root = groupId {
            return max(0, Int(limits.maxPinnedChatCount))
        } else {
            return max(0, Int(limits.maxArchivedPinnedChatCount))
        }
    }

    public static func serverVisibleItemIds(_ itemIds: [PinnedItemId], limit: Int) -> [PinnedItemId] {
        guard limit > 0 else {
            return []
        }
        var result: [PinnedItemId] = []
        result.reserveCapacity(min(limit, itemIds.count))
        for itemId in itemIds {
            switch itemId {
            case let .peer(peerId):
                if peerId.namespace == Namespaces.Peer.SecretChat {
                    continue
                }
            }
            result.append(itemId)
            if result.count >= limit {
                break
            }
        }
        return result
    }

    /// Telegram counts regular and secret-chat pins separately. When the local
    /// unlimited mode is disabled, trim both classes back to the normal limit.
    public static func clientLimitedItemIds(_ itemIds: [PinnedItemId], limit: Int) -> [PinnedItemId] {
        guard limit > 0 else {
            return []
        }
        var regularCount = 0
        var secretCount = 0
        var result: [PinnedItemId] = []
        result.reserveCapacity(min(itemIds.count, limit * 2))

        for itemId in itemIds {
            switch itemId {
            case let .peer(peerId):
                if peerId.namespace == Namespaces.Peer.SecretChat {
                    if secretCount < limit {
                        result.append(itemId)
                        secretCount += 1
                    }
                } else if regularCount < limit {
                    result.append(itemId)
                    regularCount += 1
                }
            }
        }
        return result
    }

    public static func trimToServerLimits(postbox: Postbox, accountPeerId: PeerId) -> Signal<Never, NoError> {
        return postbox.transaction { transaction -> Void in
            let groupIds: [PeerGroupId] = [.root, Namespaces.PeerGroup.archive]
            for groupId in groupIds {
                let current = transaction.getPinnedItemIds(groupId: groupId)
                let limit = serverLimit(transaction: transaction, accountPeerId: accountPeerId, groupId: groupId)
                let trimmed = clientLimitedItemIds(current, limit: limit)
                if trimmed != current {
                    transaction.setPinnedItemIds(groupId: groupId, itemIds: trimmed)
                }
            }
        }
        |> ignoreValues
    }

    public static func mergeRemoteWithLocalPins(remoteItemIds: [PinnedItemId], localItemIds: [PinnedItemId]) -> [PinnedItemId] {
        var result = remoteItemIds
        for itemId in localItemIds {
            if !result.contains(itemId) {
                result.append(itemId)
            }
        }
        return result
    }
}
