import Foundation
import Postbox
import SwiftSignalKit

/// One-shot exception for Ghost read suppression.
/// Sending a message while "online pulse on send" is enabled should behave like
/// AyuGram: briefly go online and mark the current chat as read.
public enum AyuSendPulseState {
    private struct State {
        var readReceiptDeadlineByPeer: [Int64: Double] = [:]
    }

    private static let state = Atomic<State>(value: State())
    private static let lifetime: Double = 5.0

    private static func key(_ peerId: PeerId) -> Int64 {
        return peerId.toInt64()
    }

    public static func armReadReceipt(peerId: PeerId) {
        let deadline = Date().timeIntervalSince1970 + lifetime
        _ = state.modify { current in
            var current = current
            current.readReceiptDeadlineByPeer[key(peerId)] = deadline
            return current
        }
    }

    /// Consumes the exception exactly once. An expiry prevents a failed/aborted
    /// send from accidentally leaking a later read receipt.
    public static func consumeReadReceipt(peerId: PeerId) -> Bool {
        let now = Date().timeIntervalSince1970
        var allowed = false
        _ = state.modify { current in
            var current = current
            let peerKey = key(peerId)
            if let deadline = current.readReceiptDeadlineByPeer.removeValue(forKey: peerKey), deadline >= now {
                allowed = true
            }
            if current.readReceiptDeadlineByPeer.count > 64 {
                current.readReceiptDeadlineByPeer = current.readReceiptDeadlineByPeer.filter { $0.value >= now }
            }
            return current
        }
        return allowed
    }
}
