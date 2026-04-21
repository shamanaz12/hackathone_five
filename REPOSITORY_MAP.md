

# 🗺️ TaskFlow AI Repository Flow Map
### Digital FTE — Folder Interconnectivity

This map explains how the folders in this repository interact to create the autonomous support agent.

```text
📦 hackathone_five (ROOT)
 ┃
 ┣━━ 📂 production/api/ ━━━━━━━━━━━━━━┓ 
 ┃   (Entry Point - FastAPI)          ┃
 ┃             ┃                      ┃
 ┃             ▼                      ┃
 ┃   📂 production/agent/ ◀━━━━━━━━━┓ ┃
 ┃   (The Brain - AI Logic)         ┃ ┃
 ┃             ┃                    ┃ ┃
 ┃      ┌──────┴──────┐             ┃ ┃
 ┃      ▼             ▼             ┃ ┃
 ┃   📂 src/   📂 production/       ┃ ┃
 ┃   (Tools)   database/            ┃ ┃
 ┃      ┃      (Storage)            ┃ ┃
 ┃      ▼             ┃             ┃ ┃
 ┃   [MCP SERVER] ◀───┘             ┃ ┃
 ┃             ┃                    ┃ ┃
 ┃             ▼                    ┃ ┃
 ┃   📂 production/channels/ ━━━━━━━┛ ┃
 ┃   (Connectors: Gmail & WhatsApp)   ┃
 ┃             ┃                      ┃
 ┃             ▼                      ┃
 ┗━━ 📂 support-web/ ◀━━━━━━━━━━━━━━━━┛
     (Frontend - Next.js)
```

### 🔗 Execution Flow:
1.  **Incoming:** Request hits `production/channels/` (WhatsApp/Email).
2.  **Route:** `production/api/` routes it to the `production/agent/`.
3.  **Process:** The `agent/` uses `src/` (MCP Tools) to fetch data from `database/`.
4.  **Response:** The `agent/` sends the final answer back through `channels/`.
5.  **UI:** `support-web/` provides a beautiful dashboard to view these operations.

---
*Created for TaskFlow AI — Digital FTE Factory*
