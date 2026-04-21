
# 🛠️ MCP Toolset (The Hands)
### Model Context Protocol Implementation

These tools allow the LLM to interact with the database and business logic.

```text
       AGENT REQUEST (via MCP)
              │
      ┌───────┴───────┐
      │  MCP SERVER   │
      └───────┬───────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌─────────┐
│ SEARCH│ │ TICKETS│ │ HISTORY │
│  KB   │ │ ENGINE│ │ ANALYZER│
└───────┘ └───────┘ └─────────┘
    │         │          │
    └─────────┼──────────┘
              │
      JSON TOOL RESULT
```
