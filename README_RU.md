# AyuGram iOS v0.2.2 — stability base

Это **не старый v0.1**. v0.1 напрямую подтверждал локальный read-state, обходя штатную state machine Telegram; это удалено.

## Что реально работает в v0.2.2

- Ghost master switch
- Не отправлять read receipts сообщений
- Не отправлять story views
- Не отправлять online
- Не отправлять typing/record/upload activity (кроме group-call/emoji interactions)
- Автоматический offline
- Управление из `Telegram -> Debug -> AyuGram Settings`

Ghost **OFF по умолчанию**. Пока он выключен, код ведёт себя максимально близко к официальному Telegram.

## Что будет в следующем слое

- Spy: сохранение удалённых сообщений
- история правок
- optional bot chats / read dates / last online / attachments
- полупрозрачные удалёнки
- настраиваемая метка/цвет удалённых сообщений

Эти пункты специально не имитируются фейковыми переключателями: для них нужен отдельный storage/rendering слой, иначе можно снова сломать Postbox.

## Производительность

- `UserDefaults` не читается в каждом сообщении/кадре: настройки загружаются один раз в `Atomic` snapshot.
- Никаких новых polling loops.
- Ghost online отключает создание штатного 30-секундного online refresh timer при включённом hide-online.
- Typing suppression происходит до Postbox transaction/network request.
- Read suppression оставляет штатную Telegram verification/confirmation state machine и блокирует только низкоуровневый API push.
- Story suppression завершает существующую operation-log operation штатным путём.

## Быстрый CI

`verify-patch.yml` сначала за несколько минут проверяет anchors. Если patch сломан — дорогая сборка не запускается.

`build-ipa.yml` сохраняет Bazel disk cache в GitHub Actions cache. Первый build на новом cache всё ещё может быть долгим. **Следующие сборки на том же pinned Telegram commit должны переиспользовать большую часть уже собранного графа.** Точное время зависит от cache hit/размера cache и runner.

Telegram commit фиксируется в `telegram-ref.txt`, чтобы очередной апдейт upstream не ломал patch и не сбрасывал cache без причины.


## v0.2.2.2
- Fixed Swift 6 `Atomic.modify` unused-result build error.
- Workflows can resolve Telegram-iOS HEAD when `telegram-ref.txt` is absent.


## v0.2.2
- Swift 6 fix for ignored Atomic.modify result is included.
- Build cache key now follows the actual Telegram-iOS commit even when telegram-ref.txt is absent.
- ZIP includes payload/ and both GitHub Actions workflows.
