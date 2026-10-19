import Foundation
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import AccountContext

private enum AyuSettingsPage {
    case ghost
    case messages
    case chats
}

private final class AyuRootControllerArguments {
    let openPage: (AyuSettingsPage) -> Void

    init(openPage: @escaping (AyuSettingsPage) -> Void) {
        self.openPage = openPage
    }
}

private enum AyuRootSection: Int32 {
    case categories
}

private enum AyuRootEntry: ItemListNodeEntry {
    case header
    case ghost(Bool)
    case messages
    case chats

    var section: ItemListSectionId {
        return AyuRootSection.categories.rawValue
    }

    var stableId: Int32 {
        switch self {
        case .header: return 0
        case .ghost: return 1
        case .messages: return 2
        case .chats: return 3
        }
    }

    static func <(lhs: AyuRootEntry, rhs: AyuRootEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuRootControllerArguments
        switch self {
        case .header:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "КАТЕГОРИИ", sectionId: self.section)
        case let .ghost(enabled):
            return ItemListDisclosureItem(
                presentationData: presentationData,
                systemStyle: .glass,
                title: "👻  Режим призрака",
                label: enabled ? "Включён" : "Выключен",
                sectionId: self.section,
                style: .blocks,
                action: { arguments.openPage(.ghost) }
            )
        case .messages:
            return ItemListDisclosureItem(
                presentationData: presentationData,
                systemStyle: .glass,
                title: "💬  Сообщения",
                label: "Удалённые и изменённые",
                sectionId: self.section,
                style: .blocks,
                action: { arguments.openPage(.messages) }
            )
        case .chats:
            return ItemListDisclosureItem(
                presentationData: presentationData,
                systemStyle: .glass,
                title: "📌  Чаты",
                label: "Закрепления",
                sectionId: self.section,
                style: .blocks,
                action: { arguments.openPage(.chats) }
            )
        }
    }
}

private func ayuRootEntries(_ snapshot: AyuRuntimeSnapshot) -> [AyuRootEntry] {
    return [
        .header,
        .ghost(snapshot.master),
        .messages,
        .chats
    ]
}

private final class AyuSettingsControllerArguments {
    let updateBool: (AyuRuntimeOption, Bool) -> Void
    let cycleDeletedStyle: () -> Void
    let cycleDeletedColor: () -> Void
    let clearDeleted: () -> Void
    let clearEdited: () -> Void

    init(
        updateBool: @escaping (AyuRuntimeOption, Bool) -> Void,
        cycleDeletedStyle: @escaping () -> Void,
        cycleDeletedColor: @escaping () -> Void,
        clearDeleted: @escaping () -> Void,
        clearEdited: @escaping () -> Void
    ) {
        self.updateBool = updateBool
        self.cycleDeletedStyle = cycleDeletedStyle
        self.cycleDeletedColor = cycleDeletedColor
        self.clearDeleted = clearDeleted
        self.clearEdited = clearEdited
    }
}

private enum AyuSettingsSection: Int32 {
    case ghost
    case deleted
    case edited
    case chats
}

private enum AyuSettingsEntry: ItemListNodeEntry {
    case ghostHeader
    case master(Bool)
    case read(Bool)
    case stories(Bool)
    case online(Bool)
    case typing(Bool)
    case pulse(Bool)

    case deletedHeader
    case keepDeleted(Bool)
    case showMarker(Bool)
    case markerStyle(String)
    case markerColor(String)
    case clearDeleted

    case editedHeader
    case trackEdited(Bool)
    case clearEdited

    case chatsHeader
    case unlimitedPinsInfo

    var section: ItemListSectionId {
        switch self {
        case .ghostHeader, .master, .read, .stories, .online, .typing, .pulse:
            return AyuSettingsSection.ghost.rawValue
        case .deletedHeader, .keepDeleted, .showMarker, .markerStyle, .markerColor, .clearDeleted:
            return AyuSettingsSection.deleted.rawValue
        case .editedHeader, .trackEdited, .clearEdited:
            return AyuSettingsSection.edited.rawValue
        case .chatsHeader, .unlimitedPinsInfo:
            return AyuSettingsSection.chats.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .ghostHeader: return 0
        case .master: return 1
        case .read: return 2
        case .stories: return 3
        case .online: return 4
        case .typing: return 5
        case .pulse: return 6

        case .deletedHeader: return 20
        case .keepDeleted: return 21
        case .showMarker: return 22
        case .markerStyle: return 23
        case .markerColor: return 24
        case .clearDeleted: return 25

        case .editedHeader: return 40
        case .trackEdited: return 41
        case .clearEdited: return 42

        case .chatsHeader: return 60
        case .unlimitedPinsInfo: return 61
        }
    }

    static func <(lhs: AyuSettingsEntry, rhs: AyuSettingsEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuSettingsControllerArguments
        switch self {
        case .ghostHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "РЕЖИМ ПРИЗРАКА", sectionId: self.section)
        case let .master(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Режим призрака", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.master, $0) })
        case let .read(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Не читать сообщения", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.hideReadMessages, $0) })
        case let .stories(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Не отмечать просмотр историй", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.hideReadStories, $0) })
        case let .online(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Скрывать онлайн", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.hideOnline, $0) })
        case let .typing(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Скрывать «печатает…»", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.hideTyping, $0) })
        case let .pulse(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Онлайн на 0,2 с при отправке", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.onlinePulseOnSend, $0) })

        case .deletedHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "УДАЛЁННЫЕ СООБЩЕНИЯ", sectionId: self.section)
        case let .keepDeleted(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Сохранять удалённые сообщения", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.keepDeletedMessages, $0) })
        case let .showMarker(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Показывать метку удаления", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.showDeletedMarker, $0) })
        case let .markerStyle(value):
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Стиль метки", label: value, sectionId: self.section, style: .blocks, action: { arguments.cycleDeletedStyle() })
        case let .markerColor(value):
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Цвет метки", label: value, sectionId: self.section, style: .blocks, action: { arguments.cycleDeletedColor() })
        case .clearDeleted:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Очистить метки удалённых", label: "", sectionId: self.section, style: .blocks, action: { arguments.clearDeleted() })

        case .editedHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "ИСТОРИЯ ИЗМЕНЕНИЙ", sectionId: self.section)
        case let .trackEdited(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Сохранять историю изменений", value: value, sectionId: self.section, style: .blocks, updated: { arguments.updateBool(.trackEditedMessages, $0) })
        case .clearEdited:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Очистить историю изменений", label: "", sectionId: self.section, style: .blocks, action: { arguments.clearEdited() })

        case .chatsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "ЗАКРЕПЛЁННЫЕ ЧАТЫ", sectionId: self.section)
        case .unlimitedPinsInfo:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .markdown("**Безлимитные закрепы включены.** Можно закреплять больше чатов, чем разрешяет обычный лимит Telegram. Закрепы сверх серверного лимита хранятся только на этом устройстве."),
                sectionId: self.section
            )
        }
    }
}

private func ayuPageEntries(_ page: AyuSettingsPage, snapshot: AyuRuntimeSnapshot) -> [AyuSettingsEntry] {
    switch page {
    case .ghost:
        return [
            .ghostHeader,
            .master(snapshot.master),
            .read(snapshot.hideReadMessages),
            .stories(snapshot.hideReadStories),
            .online(snapshot.hideOnline),
            .typing(snapshot.hideTyping),
            .pulse(snapshot.onlinePulseOnSend)
        ]
    case .messages:
        return [
            .deletedHeader,
            .keepDeleted(snapshot.keepDeletedMessages),
            .showMarker(snapshot.showDeletedMarker),
            .markerStyle(AyuRuntimeSettings.deletedMarkerStyleTitle),
            .markerColor(AyuRuntimeSettings.deletedMarkerColorTitle),
            .clearDeleted,
            .editedHeader,
            .trackEdited(snapshot.trackEditedMessages),
            .clearEdited
        ]
    case .chats:
        return [
            .chatsHeader,
            .unlimitedPinsInfo
        ]
    }
}

private func ayuSettingsPageController(context: AccountContext, page: AyuSettingsPage) -> ViewController {
    let revision = ValuePromise<Int32>(0, ignoreRepeated: false)
    var revisionValue: Int32 = 0
    let bump: () -> Void = {
        revisionValue &+= 1
        revision.set(revisionValue)
    }

    let arguments = AyuSettingsControllerArguments(
        updateBool: { option, value in
            AyuRuntimeSettings.set(option, value: value)
            if value {
                switch option {
                case .master, .hideOnline:
                    if AyuRuntimeSettings.suppressOnlineStatus {
                        AyuGhostLastSeen.recordNow()
                    }
                default:
                    break
                }
            }
            bump()
        },
        cycleDeletedStyle: {
            let current = AyuRuntimeSettings.snapshot.deletedMarkerStyle
            AyuRuntimeSettings.setDeletedMarkerStyle((current + 1) % 4)
            bump()
        },
        cycleDeletedColor: {
            let current = AyuRuntimeSettings.snapshot.deletedMarkerColor
            AyuRuntimeSettings.setDeletedMarkerColor((current + 1) % 4)
            bump()
        },
        clearDeleted: {
            AyuRuntimeSettings.clearDeletedMarkers()
            bump()
        },
        clearEdited: {
            AyuEditHistoryStore.clearAll()
            bump()
        }
    )

    let title: String
    switch page {
    case .ghost:
        title = "Режим призрака"
    case .messages:
        title = "Сообщения"
    case .chats:
        title = "Чаты"
    }

    let signal = combineLatest(context.sharedContext.presentationData, revision.get())
    |> deliverOnMainQueue
    |> map { presentationData, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(title),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: ayuPageEntries(page, snapshot: AyuRuntimeSettings.snapshot),
            style: .blocks,
            animateChanges: true
        )
        return (controllerState, (listState, arguments))
    }

    return ItemListController(context: context, state: signal)
}

func ayuSettingsController(context: AccountContext) -> ViewController {
    let revision = ValuePromise<Int32>(0, ignoreRepeated: false)
    var controller: ItemListController?

    let arguments = AyuRootControllerArguments(openPage: { page in
        controller?.push(ayuSettingsPageController(context: context, page: page))
    })

    let signal = combineLatest(context.sharedContext.presentationData, revision.get())
    |> deliverOnMainQueue
    |> map { presentationData, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("AyuGram"),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: ayuRootEntries(AyuRuntimeSettings.snapshot),
            style: .blocks,
            animateChanges: true
        )
        return (controllerState, (listState, arguments))
    }

    controller = ItemListController(context: context, state: signal)
    return controller!
}
