#!/usr/bin/env python3
"""Optional native network enhancements, WebKit blocking, proxy selection and profile metadata."""
from pathlib import Path
import argparse

MARK = "AYU_NETWORK_TOOLS_v1"
CORE = "submodules/TelegramCore/Sources/"
PEER = "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"

def once(s, old, new, label):
    if s.count(old) != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {s.count(old)}")
    return s.replace(old, new, 1)

def upload(s):
    return once(s, """        if increaseParallelParts {
            self.parallelParts = 30
        } else {
            self.parallelParts = 3
        }""", """        // AYU_NETWORK_TOOLS_v1: preserve encrypted uploads and stock aggressive mode.
        if increaseParallelParts {
            self.parallelParts = 30
        } else if AyuNetworkSettings.enabled(.fastUpload), encryptionKey == nil, !forceNoBigParts,
                  hintFileIsLarge || (hintFileSize ?? 0) > 1024 * 1024 {
            self.parallelParts = 12
        } else {
            self.parallelParts = 3
        }""", "upload")

def fetch(s):
    s = once(s, """            if isStory {
                self.defaultPartSize = 512 * 1024
            } else {
                self.defaultPartSize = 128 * 1024
            }""", """            // AYU_NETWORK_TOOLS_v1: larger chunks for large unencrypted files.
            if isStory || (AyuNetworkSettings.enabled(.fastDownload) && encryptionKey == nil && (size ?? 0) >= 2 * 1024 * 1024) {
                self.defaultPartSize = 512 * 1024
            } else {
                self.defaultPartSize = 128 * 1024
            }""", "fetch size")
    s = once(s, """                    maxPendingParts: 6,
                    decryptionState: decryptionState""", """                    maxPendingParts: AyuNetworkSettings.enabled(.fastDownload) && self.encryptionKey == nil && (self.size ?? 0) >= 2 * 1024 * 1024 ? 12 : 6,
                    decryptionState: decryptionState""", "fetch parallel")
    return s

def legacy(s):
    return once(s, "                self.parallelParts = 8\n", """                // AYU_NETWORK_TOOLS_v1: only large ordinary files.
                self.parallelParts = AyuNetworkSettings.enabled(.fastDownload) && encryptionKey == nil && size >= 2 * 1024 * 1024 ? 16 : 8
""", "legacy fetch")

def account(s):
    return once(s, """        if !supplementary {
            let mediaBox = postbox.mediaBox
            let _ = (accountManager.sharedData(keys: [SharedDataKeys.cacheStorageSettings])""", """        if !supplementary {
            // AYU_NETWORK_TOOLS_v1: proxy monitor disposed with this account.
            self.managedOperationsDisposable.add(ayuManagedAutoProxy(accountManager: accountManager, network: network))
            let mediaBox = postbox.mediaBox
            let _ = (accountManager.sharedData(keys: [SharedDataKeys.cacheStorageSettings])""", "account monitor")

def settings(s):
    # Root-only entry; existing categories retain their exact behavior.
    s = once(s, """private enum AyuSettingsPage {
    case ghost
    case messages
    case premium
    case chats
}""", """private enum AyuSettingsPage {
    case ghost
    case messages
    case premium
    case chats
    case network
}""", "page")
    s = once(s, """    case header
    case ghost(Bool)
    case messages
    case premium
    case chats
""", """    case header
    case ghost(Bool)
    case messages
    case premium
    case chats
    case network
""", "root entry")
    s = once(s, "        case .chats: return 4\n", "        case .chats: return 4\n        case .network: return 5\n", "root id")
    s = once(s, """        case .chats:
            return ItemListDisclosureItem(""", """        // AYU_NETWORK_TOOLS_v1: new root category.
        case .network:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Сеть и браузер", label: "", sectionId: self.section, style: .blocks, action: { arguments.openPage(.network) })
        case .chats:
            return ItemListDisclosureItem(""", "root row")
    s = once(s, """        .premium,
        .chats
    ]""", """        .premium,
        .chats,
        .network
    ]""", "root list")
    s = once(s, """    case .chats:
        return [
            .chatsHeader,""", """    case .network:
        return []
    case .chats:
        return [
            .chatsHeader,""", "entry exhaustiveness")
    s = once(s, """    case .chats:
        title = "Чаты"
""", """    case .chats:
        title = "Чаты"
    case .network:
        title = "Сеть и браузер"
""", "title")
    return once(s, "        controller?.push(ayuSettingsPageController(context: context, page: page))", """        if case .network = page {
            controller?.push(ayuNetworkSettingsController(context: context))
        } else {
            controller?.push(ayuSettingsPageController(context: context, page: page))
        }""", "navigation")

def profile(s):
    # Registration month comes from Telegram's own peerSettings, no ID guessing
    # and no external lookup of the user's contacts.
    anchor = "        if let phone = user.phone ?? ayuCachedProfile.phone {\n"
    return once(s, anchor, """        // AYU_NETWORK_TOOLS_v1: Telegram only exposes month/year for some users.
        if AyuNetworkSettings.enabled(.registrationDate), user.botInfo == nil {
            let registration = AyuNetworkSettings.registrationMonth((data.cachedData as? CachedUserData)?.peerStatusSettings?.registrationDate)
            items[currentPeerInfoSection]!.append(PeerInfoScreenLabeledValueItem(
                id: 3019, label: "Дата регистрации", text: registration ?? "Нет данных от Telegram",
                textColor: .primary, action: nil, longTapAction: nil, contextAction: nil,
                requestLayout: { animated in interaction.requestLayout(animated) }
            ))
        }
""" + anchor, "profile")

def browser(s):
    # Only the Telegram browser. Do not alter mini apps, payment webviews or Safari.
    return once(s, """        if let request {
            self.webView.load(request)
        }
""", r'''        if let request {
            // AYU_NETWORK_TOOLS_v1: install a native WebKit content rule before the first page load.
            if #available(iOS 11.0, *), request.url?.scheme?.hasPrefix("http") == true {
                let store = WKContentRuleListStore.default()
                let identifier = "ayu.browser.adblock.v1"
                let contentController = self.webView.configuration.userContentController
                let shouldBlock = AyuNetworkSettings.enabled(.browserAdBlock)
                let load: (WKContentRuleList?) -> Void = { [weak self] rules in
                    DispatchQueue.main.async {
                        if let rules {
                            contentController.remove(rules)
                            if shouldBlock { contentController.add(rules) }
                        }
                        self?.webView.load(request)
                    }
                }
                store.lookUpContentRuleList(forIdentifier: identifier) { existing, _ in
                    if let existing {
                        load(existing)
                    } else if shouldBlock {
                        let domains = ["doubleclick.net", "googlesyndication.com", "googleadservices.com", "adnxs.com", "adsrvr.org", "rubiconproject.com", "openx.net", "pubmatic.com", "criteo.com", "criteo.net", "taboola.com", "outbrain.com", "amazon-adsystem.com", "advertising.com", "moatads.com"]
                        let pattern = "^https?://([^/]+\\.)?(" + domains.map { $0.replacingOccurrences(of: ".", with: "\\.") }.joined(separator: "|") + ")([:/]|$)"
                        let rules: [[String: Any]] = [
                            ["trigger": ["url-filter": pattern, "load-type": ["third-party"]], "action": ["type": "block"]]
                        ]
                        if let data = try? JSONSerialization.data(withJSONObject: rules), let json = String(data: data, encoding: .utf8) {
                            store.compileContentRuleList(forIdentifier: identifier, encodedContentRuleList: json) { compiled, _ in load(compiled) }
                        } else {
                            load(nil)
                        }
                    } else {
                        load(nil)
                    }
                }
            } else {
                self.webView.load(request)
            }
        }
''', "browser")

def apply(path, transform):
    src = path.read_text(encoding="utf-8")
    if MARK in src:
        if src.count(MARK) != 1:
            raise RuntimeError(f"Duplicate marker in {path}")
        return
    dst = transform(src)
    if dst.count(MARK) != 1:
        raise RuntimeError(f"Missing marker in {path}")
    path.write_text(dst, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("telegram_repo", type=Path)
    root = parser.parse_args().telegram_repo.resolve()
    payload = Path(__file__).resolve().parent / "payload"
    for name, relative in (
        ("AyuNetworkSettings.swift", CORE + "State/AyuNetworkSettings.swift"),
        ("AyuNetworkSettingsController.swift", PEER + "AyuNetworkSettingsController.swift"),
    ):
        (root / relative).write_text((payload / name).read_text(encoding="utf-8"), encoding="utf-8")
    for relative, transform in (
        (CORE + "Network/MultipartUpload.swift", upload),
        (CORE + "Network/FetchV2.swift", fetch),
        (CORE + "Network/MultipartFetch.swift", legacy),
        (CORE + "Account/Account.swift", account),
        (PEER + "AyuSettingsController.swift", settings),
        (PEER + "PeerInfoProfileItems.swift", profile),
        ("submodules/BrowserUI/Sources/BrowserWebContent.swift", browser),
    ):
        apply(root / relative, transform)
    print("[ayu-network] all enhancements applied")

if __name__ == "__main__":
    main()
