import Foundation
import SwiftSignalKit

/// Client-side sponsored-message visibility for the AyuGram iOS fork.
/// This does not change the Telegram account's Premium state; it only prevents
/// the client from loading/displaying Telegram sponsored messages.
public enum AyuAdsSettings {
    private static let key = "com.nomadvorga.telegram.ayu.v03.hideAds"

    private static func load() -> Bool {
        return UserDefaults.standard.bool(forKey: key)
    }

    private static let state = Atomic<Bool>(value: load())

    public static var hideAds: Bool {
        return state.with { $0 }
    }

    public static func setHideAds(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: key)
        _ = state.modify { _ in value }
    }
}
