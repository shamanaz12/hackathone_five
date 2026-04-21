
# 🧠 Agent Brain Architecture
### TaskFlow AI — Customer Success FTE

This directory contains the core logic of the Digital Worker. It handles the transition from raw input to intelligent action.

```text
       INCOMING INQUIRY
              │
      ┌───────▼───────┐
      │  NORMALIZE    │──▶ Strip noise, detect language
      └───────┬───────┘
              │
      ┌───────▼───────┐
      │  CLASSIFY     │──▶ Billing, Technical, Sales, or General
      └───────┬───────┘
              │
      ┌───────▼───────┐       ┌────────────────────────┐
      │ TOOL CALLING  │◀─────▶│   MCP SERVER TOOLS     │
      │    LOOP       │       │ (KB, History, Tickets) │
      └───────┬───────┘       └────────────────────────┘
              │
      ┌───────▼───────┐
      │  ADAPTATION   │──▶ Format for Gmail vs WhatsApp
      └───────┬───────┘
              │
       FINAL RESPONSE
```
