
# 🗄️ System Memory
### PostgreSQL & Data Persistence

How TaskFlow remembers customers and tracks every interaction.

```text
    ┌─────────────────┐
    │    CUSTOMERS    │──┐
    └─────────────────┘  │   ┌─────────────────┐
                         ├──▶│     TICKETS     │
    ┌─────────────────┐  │   └────────┬────────┘
    │  CONVERSATIONS  │──┘            │
    └─────────────────┘               ▼
                             ┌─────────────────┐
                             │   ESCALATIONS   │
                             └─────────────────┘

  [ ASYNC I/O ] ◀──▶ [ REPOSITORIES ] ◀──▶ [ MODELS ]
```
