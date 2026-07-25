
# 🗺️ TaskFlow AI: Digital FTE System Map
### Comprehensive Architectural & Folder Flow

This document provides a high-fidelity visual map of the TaskFlow AI Support Agent. It illustrates how incoming requests from WhatsApp, Gmail, and Web Forms are processed by the AI Brain, managed via MCP tools, and persisted in the Real-Base SQLite database.

## 🏗️ System Architecture

```mermaid
graph TB
    %% Definitions
    subgraph "External Channels"
        WC[WhatsApp Cloud API]
        GC[Gmail API / PubSub]
        WF[React Web Form]
    end

    subgraph "API & Routing (production/api/)"
        FAST[FastAPI Server]
        WH[Webhooks]
        REST[REST Endpoints]
    end

    subgraph "AI Brain (production/agent/)"
        AP[Agent Pipeline]
        PROMPT[System Prompts]
        SA[Sentiment Analysis]
    end

    subgraph "Logic & Tools (src/)"
        MCP[MCP Server]
        TOOL1[KB Search]
        TOOL2[Ticket Creation]
        TOOL3[History Lookup]
    end

    subgraph "Persistence (production/database/)"
        DB[(taskflow.db - SQLite)]
        REPO[Repositories]
        MODELS[SQLAlchemy Models]
    end

    subgraph "Frontend (support-web/)"
        DASH[Admin Dashboard]
        COMP[Support Form Components]
    end

    %% Flow Connections
    WC -->|Webhook POST| WH
    GC -->|Webhook POST| WH
    WF -->|API Call| REST
    
    WH --> FAST
    REST --> FAST
    
    FAST -->|Inquiry| AP
    AP -->|Context| PROMPT
    AP -->|Action| MCP
    
    MCP -->|Call Tool| TOOL1
    MCP -->|Call Tool| TOOL2
    MCP -->|Call Tool| TOOL3
    
    TOOL1 --> REPO
    TOOL2 --> REPO
    TOOL3 --> REPO
    
    REPO --> DB
    MODELS --- DB

    DASH -->|Read Data| REST
    COMP -->|Submit| WF

    %% Styling
    classDef channel fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef api fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef brain fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef tools fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
    classDef database fill:#efebe9,stroke:#3e2723,stroke-width:2px;
    
    class WC,GC,WF channel;
    class FAST,WH,REST api;
    class AP,PROMPT,SA brain;
    class MCP,TOOL1,TOOL2,TOOL3 tools;
    class DB,REPO,MODELS database;
```

## 📂 Folder-to-Function Mapping

| Folder Path | Function | Description |
|:---|:---|:---|
| `production/api/` | **Entry Point** | FastAPI app, webhooks, and routing logic. |
| `production/agent/` | **AI Reasoning** | Agent pipeline, multi-model prompts, and sentiment analysis. |
| `production/channels/` | **I/O Handlers** | Specific logic for Gmail and WhatsApp APIs. |
| `src/` | **Tool Layer** | Model Context Protocol (MCP) server and implementation. |
| `production/database/` | **Real-Base** | SQLite schema, repository patterns, and persistent storage. |
| `support-web/` | **UI/UX** | Next.js/Tailwind dashboard for monitoring support tickets. |
| `production/workers/` | **Async Processing** | Kafka-ready workers for message queues. |

## 🔄 Interaction Sequence

1. **TRIGGER:** A customer sends a WhatsApp message or Email.
2. **INGEST:** The `channels/` handler parses the payload and sends it to the `api/`.
3. **THINK:** The `agent/` pipeline analyzes sentiment and decides which MCP tool to call.
4. **ACT:** The `src/mcp_server.py` executes a tool (e.g., search knowledge base).
5. **STORE:** Data is saved to the `taskflow.db` using `production/database/` repos.
6. **RESPOND:** The AI generates a brand-compliant reply and sends it back through the channel.

---
*Generated for TaskFlow AI Final Hackathon Submission — 2026*
