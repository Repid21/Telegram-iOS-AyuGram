import Foundation
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import AccountContext

private final class AyuNetworkArguments {
    let change: (AyuNetworkOption, Bool) -> Void
    let source: (String) -> Void
    let openProxies: () -> Void
    init(change: @escaping (AyuNetworkOption, Bool) -> Void, source: @escaping (String) -> Void, openProxies: @escaping () -> Void) {
        self.change = change
        self.source = source
        self.openProxies = openProxies
    }
}

private enum AyuNetworkEntry: ItemListNodeEntry {
    case header(Int32, String)
    case toggle(Int32, AyuNetworkOption, String, Bool)
    case info(Int32, String)
    case source(String)
    case proxies

    var stableId: Int32 {
        switch self {
        case let .header(id, _), let .info(id, _): return id
        case let .toggle(id, _, _, _): return id
        case .source: return 24
        case .proxies: return 25
        }
    }
    var section: ItemListSectionId { return self.stableId / 10 }
    static func < (lhs: AyuNetworkEntry, rhs: AyuNetworkEntry) -> Bool { return lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let args = arguments as! AyuNetworkArguments
        switch self {
        case let .header(_, title):
            return ItemListSectionHeaderItem(presentationData: presentationData, text: title, sectionId: self.section)
        case let .toggle(_, key, title, value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: title, value: value, sectionId: self.section, style: .blocks, updated: { args.change(key, $0) })
        case let .info(_, text):
            return ItemListTextItem(presentationData: presentationData, text: .markdown(text), sectionId: self.section)
        case let .source(value):
            return ItemListSingleLineInputItem(presentationData: presentationData, systemStyle: .glass, title: NSAttributedString(string: ""), text: value, placeholder: "https://…/proxies.txt", type: .regular(capitalization: false, autocorrection: false), spacing: 0.0, sectionId: self.section, textUpdated: { args.source($0) }, action: {})
        case .proxies:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Сохранённые прокси", label: "", sectionId: self.section, style: .blocks, action: args.openProxies)
        }
    }
}

func ayuNetworkSettingsController(context: AccountContext) -> ViewController {
    let revision = ValuePromise<Int32>(0, ignoreRepeated: false)
    var value: Int32 = 0
    weak var controller: ItemListController?
    let arguments = AyuNetworkArguments(change: { option, enabled in
        AyuNetworkSettings.set(option, enabled)
        value &+= 1
        revision.set(value)
    }, source: { source in
        AyuNetworkSettings.setSource(source)
    }, openProxies: {
        controller?.push(context.sharedContext.makeProxySettingsController(context: context))
    })
    let signal = combineLatest(context.sharedContext.presentationData, revision.get())
    |> deliverOnMainQueue
    |> map { presentationData, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let p = ItemListPresentationData(presentationData)
        let entries: [AyuNetworkEntry] = [
            .header(0, "ПЕРЕДАЧА ФАЙЛОВ"),
            .toggle(1, .fastDownload, "Ускорить скачивание", AyuNetworkSettings.enabled(.fastDownload)),
            .toggle(2, .fastUpload, "Ускорить отправку", AyuNetworkSettings.enabled(.fastUpload)),
            .info(3, "Больше параллельных частей для новых крупных загрузок. Может увеличить расход батареи и трафика; скорость зависит от сети и сервера."),
            .header(10, "БРАУЗЕР"),
            .toggle(11, .browserAdBlock, "Блокировать рекламу в браузере", AyuNetworkSettings.enabled(.browserAdBlock)),
            .info(12, "Блокирует известные сторонние рекламные домены. Открой страницу заново после изменения."),
            .header(20, "АВТОПРОКСИ"),
            .toggle(21, .autoProxy, "Искать и подключать прокси", AyuNetworkSettings.enabled(.autoProxy)),
            .toggle(22, .skipVPN, "Не подключать прокси при VPN", AyuNetworkSettings.enabled(.skipVPN)),
            .info(23, "Проверяются сохранённые серверы и указанный ниже HTTPS-список MTProto (по одной ссылке t.me/proxy на строку). Используй только доверенный источник. Проверка VPN на iOS приблизительная."),
            .source(AyuNetworkSettings.source),
            .proxies,
            .header(30, "ПРОФИЛЬ"),
            .toggle(31, .registrationDate, "Показывать дату регистрации", AyuNetworkSettings.enabled(.registrationDate)),
            .info(32, "Показывает месяц и год, если Telegram предоставил их. Точная дата не доступна; если данных нет, так и будет написано.")
        ]
        let state = ItemListControllerState(presentationData: p, title: .text("Сеть и браузер"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        return (state, (ItemListNodeState(presentationData: p, entries: entries, style: .blocks, animateChanges: true), arguments))
    }
    let result = ItemListController(context: context, state: signal)
    controller = result
    return result
}
