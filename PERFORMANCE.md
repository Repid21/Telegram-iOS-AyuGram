# Performance rules

1. Feature OFF = one cheap in-memory Atomic check and stock Telegram path.
2. No per-frame allocations from Ayu features.
3. No new periodic timers or network polling.
4. Future Spy storage: separate auxiliary DB/queue, batched writes, bounded attachment cache.
5. Deleted-mark rendering: only visible message items, O(1) cached metadata lookup; no whole-chat scan per frame.
6. New features are added only after the previous layer survives normal chats, folders, profiles, contacts and message sending without crashes.
