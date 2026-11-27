import Foundation
import CFNetwork
import Postbox
import SwiftSignalKit
import MtProtoKit

// AYU_NETWORK_TOOLS_v1: local, opt-in network settings; never change server limits.
public enum AyuNetworkOption: String {
    case fastDownload, fastUpload, browserAdBlock, autoProxy, skipVPN, registrationDate
}

public enum AyuNetworkSettings {
    private static let prefix = "com.nomadvorga.telegram.ayu.network.v1."
    public static func enabled(_ option: AyuNetworkOption) -> Bool {
        let defaults = UserDefaults.standard
        let key = prefix + option.rawValue
        return defaults.object(forKey: key) == nil ? (option == .skipVPN || option == .registrationDate) : defaults.bool(forKey: key)
    }

    public static func set(_ option: AyuNetworkOption, _ value: Bool) {
        UserDefaults.standard.set(value, forKey: prefix + option.rawValue)
    }

    public static var source: String {
        return UserDefaults.standard.string(forKey: prefix + "source") ?? ""
    }

    public static func setSource(_ value: String) {
        UserDefaults.standard.set(value.trimmingCharacters(in: .whitespacesAndNewlines), forKey: prefix + "source")
    }

    // iOS does not expose an authoritative status for every third-party VPN.
    // Recognize scoped tunnel interfaces; err on the side of not auto-connecting
    // if the system proxy information itself is unavailable.
    public static var vpnLikelyActive: Bool {
        guard let settings = CFNetworkCopySystemProxySettings()?.takeRetainedValue() as? [String: Any] else {
            return true
        }
        guard let scoped = settings["__SCOPED__"] as? [String: Any] else {
            return false
        }
        return scoped.keys.contains { key in
            let name = key.lowercased()
            return ["utun", "tun", "tap", "ipsec", "ppp", "wg"].contains(where: { name.hasPrefix($0) })
        }
    }

    static var skipAutomaticProxy: Bool {
        return !enabled(.autoProxy) || (enabled(.skipVPN) && vpnLikelyActive)
    }

    static var ownedProxy: ProxyServerSettings? {
        guard let data = UserDefaults.standard.data(forKey: prefix + "owned") else { return nil }
        return try? JSONDecoder().decode(ProxyServerSettings.self, from: data)
    }

    static func rememberOwnedProxy(_ value: ProxyServerSettings?) {
        if let value, let data = try? JSONEncoder().encode(value) {
            UserDefaults.standard.set(data, forKey: prefix + "owned")
        } else {
            UserDefaults.standard.removeObject(forKey: prefix + "owned")
        }
    }

    public static func registrationMonth(_ raw: String?) -> String? {
        guard let raw else { return nil }
        let fields = raw.split(separator: ".")
        guard fields.count == 2, let month = Int(fields[0]), let year = Int(fields[1]),
              (1 ... 12).contains(month), (2013 ... Calendar.current.component(.year, from: Date())).contains(year) else {
            return nil
        }
        let months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return "\(months[month - 1]) \(year)"
    }
}

private func ayuProxyCandidates(_ text: String) -> [ProxyServerSettings] {
    var result: [ProxyServerSettings] = []
    for token in text.components(separatedBy: .whitespacesAndNewlines).prefix(300) {
        guard result.count < 12 else { break }
        let value = token.replacingOccurrences(of: "&amp;", with: "&")
        guard let url = URLComponents(string: value) else { continue }
        let isTelegram = (url.scheme == "https" && url.host?.lowercased() == "t.me" && url.path == "/proxy") ||
                         (url.scheme == "tg" && url.host?.lowercased() == "proxy")
        guard isTelegram, url.user == nil, url.password == nil else { continue }
        let query = url.queryItems ?? []
        func field(_ key: String) -> String? {
            let matches = query.filter { $0.name == key }
            return matches.count == 1 ? matches[0].value : nil
        }
        guard let host = field("server"), !host.isEmpty, host.count <= 253,
              host.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              let portText = field("port"), let port = Int32(portText), (1 ... 65535).contains(port),
              let secret = field("secret"), secret.count <= 512,
              let parsed = MTProxySecret.parse(secret) else { continue }
        let server = ProxyServerSettings(host: host, port: port, connection: .mtp(secret: parsed.serialize()))
        if !result.contains(server) { result.append(server) }
    }
    return result
}

// Only fetch an explicitly configured HTTPS list, without cookies/account data.
// Format: one t.me/proxy or tg://proxy link per line.
private func ayuDiscoverProxies() -> Signal<[ProxyServerSettings], NoError> {
    guard !AyuNetworkSettings.skipAutomaticProxy,
          let url = URL(string: AyuNetworkSettings.source), url.scheme?.lowercased() == "https",
          url.host != nil, url.user == nil, url.password == nil else {
        return .single([])
    }
    return Signal { subscriber in
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 8.0
        configuration.timeoutIntervalForResource = 12.0
        configuration.httpShouldSetCookies = false
        configuration.urlCredentialStorage = nil
        let session = URLSession(configuration: configuration)
        let task = session.dataTask(with: url) { data, response, _ in
            var result: [ProxyServerSettings] = []
            if let http = response as? HTTPURLResponse, (200 ... 299).contains(http.statusCode),
               http.url?.scheme?.lowercased() == "https", let data, data.count <= 256 * 1024,
               let body = String(data: data, encoding: .utf8), !AyuNetworkSettings.skipAutomaticProxy {
                result = ayuProxyCandidates(body)
            }
            subscriber.putNext(result)
            subscriber.putCompletion()
            session.finishTasksAndInvalidate()
        }
        task.resume()
        return ActionDisposable {
            task.cancel()
            session.invalidateAndCancel()
        }
    }
}

// Account-owned lifecycle. Only replace a proxy we selected ourselves, or activate
// one when the native proxy setting is disabled. Never replace a manual selection.
func ayuManagedAutoProxy(accountManager: AccountManager<TelegramAccountManagerTypes>, network: Network) -> Disposable {
    let work = MetaDisposable()
    let timer = DispatchSource.makeTimerSource(queue: DispatchQueue(label: "ayu.auto.proxy"))
    let timeoutQueue = Queue()
    timer.schedule(deadline: .now() + 3.0, repeating: 45.0)
    timer.setEventHandler {
        if AyuNetworkSettings.skipAutomaticProxy {
            // Undo only an automatically selected server, not the user's manual proxy.
            if let owned = AyuNetworkSettings.ownedProxy {
                work.set(updateProxySettingsInteractively(accountManager: accountManager) { current in
                    var current = current
                    if current.enabled && current.activeServer == owned {
                        current.enabled = false
                    }
                    AyuNetworkSettings.rememberOwnedProxy(nil)
                    return current
                }.start())
            } else {
                work.set(nil)
            }
            return
        }
        let settings = accountManager.sharedData(keys: [SharedDataKeys.proxySettings])
        |> take(1)
        |> map { data -> ProxySettings in
            return data.entries[SharedDataKeys.proxySettings]?.get(ProxySettings.self) ?? .defaultSettings
        }
        work.set((settings
        |> mapToSignal { current -> Signal<(ProxySettings, [ProxyServerSettings: ProxyServerStatus]), NoError> in
            if current.enabled && current.activeServer != AyuNetworkSettings.ownedProxy {
                return .complete()
            }
            return ayuDiscoverProxies()
            |> mapToSignal { discovered -> Signal<(ProxySettings, [ProxyServerSettings: ProxyServerStatus]), NoError> in
                if AyuNetworkSettings.skipAutomaticProxy { return .complete() }
                var candidates = Array(current.servers.prefix(12))
                if let active = current.activeServer, !candidates.contains(active) { candidates.insert(active, at: 0) }
                for candidate in discovered where !candidates.contains(candidate) {
                    if candidates.count >= 20 { break }
                    candidates.append(candidate)
                }
                if candidates.isEmpty { return .complete() }
                let statuses = ProxyServersStatuses(network: network, servers: .single(candidates))
                return statuses.statuses()
                |> filter { values in
                    return candidates.allSatisfy { candidate in
                        guard let status = values[candidate] else { return false }
                        if case .checking = status { return false }
                        return true
                    }
                }
                |> take(1)
                |> timeout(18.0, queue: timeoutQueue, alternate: .single([:]))
                |> map { (current, $0) }
            }
        }
        |> mapToSignal { observed, values -> Signal<Bool, NoError> in
            if AyuNetworkSettings.skipAutomaticProxy { return .complete() }
            let ranked = values.compactMap { pair -> (ProxyServerSettings, Double)? in
                if case let .available(rtt) = pair.value, rtt.isFinite, rtt >= 0 { return (pair.key, rtt) }
                return nil
            }.sorted { $0.1 < $1.1 }
            guard let best = ranked.first else { return .complete() }
            // Keep a healthy active proxy to avoid disruptive switching on every poll.
            if observed.enabled, let active = observed.activeServer,
               case .available? = values[active] { return .complete() }
            return updateProxySettingsInteractively(accountManager: accountManager) { latest in
                guard latest == observed, !AyuNetworkSettings.skipAutomaticProxy else { return latest }
                var updated = latest
                if !updated.servers.contains(best.0) { updated.servers.append(best.0) }
                updated.activeServer = best.0
                updated.enabled = true
                AyuNetworkSettings.rememberOwnedProxy(best.0)
                return updated
            }
        }).start())
    }
    timer.resume()
    return ActionDisposable {
        timer.cancel()
        work.dispose()
    }
}
