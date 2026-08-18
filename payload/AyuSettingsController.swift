import Foundation
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import AccountContext

private final class AyuSettingsControllerArguments {
    let updateBool: (AyuRuntimeOption, Bool) -> Void
    let cycleDeletedStyle: () -> Void
    let cycleDeletedColor: () -> Void
    let clearDeleted: () -> Void

    init(
        updateBool: @escaping (AyuRuntimeOption, Bool) -> Void,
        cycleDeletedStyle: @escaping () -> Void,
        cycleDeletedColor: @escaping () -> Void,
        clearDeleted: @escaping () -> Void
    ) {
        self.updateBool = updateBool
        self.cycleDeletedStyle = cycleDeletedStyle
        self.cycleDeletedColor = cycleDeletedColor
        self.clearDeleted = clearDeleted
    }
}

private enum AyuSettingsSection: Int32 {
    case ghost
    case deleted
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

    var section: ItemListSectionId {
        switch self {
        case .ghostHeader, .master, .read, .stories, .online, .typing, .pulse:
            return AyuSettingsSection.ghost.rawValue
        case .deletedHeader, .keepDeleted, .showMarker, .markerStyle, .markerColor, .clearDeleted:
            return AyuSettingsSection.deleted.rawValue
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
        case .deletedHeader: return 10
        case .keepDeleted: return 11
        case .showMarker: return 12
        case .markerStyle: return 13
        case .markerColor: return 14
        case .clearDeleted: return 15
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
        }
    }
}

private func ayuSettingsEntries(_ snapshot: AyuRuntimeSnapshot) -> [AyuSettingsEntry] {
    return [
        .ghostHeader,
        .master(snapshot.master),
        .read(snapshot.hideReadMessages),
        .stories(snapshot.hideReadStories),
        .online(snapshot.hideOnline),
        .typing(snapshot.hideTyping),
        .pulse(snapshot.onlinePulseOnSend),
        .deletedHeader,
        .keepDeleted(snapshot.keepDeletedMessages),
        .showMarker(snapshot.showDeletedMarker),
        .markerStyle(AyuRuntimeSettings.deletedMarkerStyleTitle),
        .markerColor(AyuRuntimeSettings.deletedMarkerColorTitle),
        .clearDeleted
    ]
}

func ayuSettingsController(context: AccountContext) -> ViewController {
    let revision = ValuePromise<Int32>(0, ignoreRepeated: false)
    var revisionValue: Int32 = 0
    let bump: () -> Void = {
        revisionValue &+= 1
        revision.set(revisionValue)
    }

    let arguments = AyuSettingsControllerArguments(
        updateBool: { option, value in
            AyuRuntimeSettings.set(option, value: value)
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
        }
    )

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
            entries: ayuSettingsEntries(AyuRuntimeSettings.snapshot),
            style: .blocks,
            animateChanges: true
        )
        return (controllerState, (listState, arguments))
    }

    return ItemListController(context: context, state: signal)
}
