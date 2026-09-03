import Foundation
import Postbox

/// Local unlimited pins for AyuGram iOS.
/// Telegram's server still enforces the account pin limit; only the first
/// server-visible pins are synchronized. Overflow pins stay on this device.
public enum AyuUnlimitedPins {
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
