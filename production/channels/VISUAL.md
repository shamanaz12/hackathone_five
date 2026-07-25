
# 📡 Communication Channels
### Multi-Channel Message Processing

This directory handles the "Real World" connection to customers via different platforms.

```text
  [ EXTERNAL WORLD ]          [ TASKFLOW INTERNALS ]
          │                           │
  📧 GMAIL WEBHOOK   ─────┐           │
          │               │     ┌─────────────┐
  📱 WHATSAPP API    ─────┼────▶│ AGENT PIPELINE │
          │               │     └──────┬──────┘
  🌐 WEB FORM        ─────┘           │
          │                           │
          │             ◀─────────────┘
          ▼
   INTELLIGENT REPLY
  (Formatted per channel)
```
