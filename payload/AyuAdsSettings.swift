import Foundation
import SwiftSignalKit

/// Client-side Premium helpers for the AyuGram iOS fork.
/// These options do not change Telegram's server-side Premium state.
public enum AyuAdsSettings {
    private static let hideAdsKey = "com.nomadvorga.telegram.ayu.v03.hideAds"
    private static let unlockPremiumIconsKey = "com.nomadvorga.telegram.ayu.v03.unlockPremiumIcons"

    private static let initialHideAds = UserDefaults.standard.bool(forKey: hideAdsKey)
    private static let initialUnlockPremiumIcons = UserDefaults.standard.bool(forKey: unlockPremiumIconsKey)

    private static let hideAdsState = Atomic<Bool>(value: initialHideAds)
    private static let hideAdsPromise = ValuePromise<Bool>(initialHideAds, ignoreRepeated: true)
    private static let unlockPremiumIconsState = Atomic<Bool>(value: initialUnlockPremiumIcons)

    public static var hideAds: Bool {
        return hideAdsState.with { $0 }
    }

    /// Used by already-open chat / gallery ad contexts so enabling the toggle
    /// hides sponsored messages immediately, without requiring a relaunch.
    public static var hideAdsSignal: Signal<Bool, NoError> {
        return hideAdsPromise.get()
    }

    public static func setHideAds(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: hideAdsKey)
        _ = hideAdsState.modify { _ in value }
        hideAdsPromise.set(value)
    }

    public static var unlockPremiumIcons: Bool {
        return unlockPremiumIconsState.with { $0 }
    }

    public static func setUnlockPremiumIcons(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: unlockPremiumIconsKey)
        _ = unlockPremiumIconsState.modify { _ in value }
    }
}
