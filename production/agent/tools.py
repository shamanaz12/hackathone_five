"""
TaskFlow AI Support Agent — OpenAI Agents SDK Function Tools
Production package for the CRM Digital FTE Factory Final Hackathon 5.

Connects to the MCP Server (src/mcp_server.py) for all tool operations.
This ensures a single source of truth — no duplicated logic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

try:
    from agents import function_tool
except ImportError:
    def function_tool(fn):
        """Passthrough decorator when agents SDK is not installed."""
        fn._is_agent_tool = True
        return fn

# ── Import MCP server tool functions (single source of truth) ──
import sys
from pathlib import Path
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.mcp_server import (
    search_knowledge_base as _mcp_search_kb,
    create_ticket as _mcp_create_ticket,
    get_customer_history as _mcp_get_customer_history,
    escalate_to_human as _mcp_escalate_to_human,
    send_response as _mcp_send_response,
)

# Alias for internal access in agent fallback
search_kb_raw = _mcp_search_kb
create_ticket_raw = _mcp_create_ticket
get_history_raw = _mcp_get_customer_history
escalate_raw = _mcp_escalate_to_human
send_response_raw = _mcp_send_response

from production.utils.helpers import (
    format_for_channel,
    sanitize_input,
    generate_ticket_id,
    generate_customer_id,
    generate_escalation_id,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class EscalationTeam(str, Enum):
    SECURITY = "security"
    ENGINEERING = "engineering"
    BILLING = "billing"
    SALES = "sales"
    SUPPORT = "support"
    CUSTOMER_SUCCESS = "customer_success"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


# ============================================================
# PYDANTIC INPUT MODELS
# ============================================================

class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Customer question or issue.")
    topic: str | None = Field(default=None, description="Optional topic filter.")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v):
        if v is not None:
            valid = {"password_reset", "create_project", "invite_team_members", "kanban_board", "pricing"}
            if v not in valid:
                raise ValueError(f"topic must be one of {valid}, got '{v}'")
        return v


class CreateTicketInput(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200, description="Customer full name.")
    message: str = Field(..., min_length=1, max_length=10000, description="Customer support message.")
    channel: str = Field(..., description="Channel: email, whatsapp, web_form.")
    email: str | None = Field(default=None, description="Customer email.")
    phone: str | None = Field(default=None, description="Customer phone.")
    subject: str | None = Field(default=None, max_length=500, description="Ticket subject.")

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v):
        valid = {c.value for c in Channel}
        if v.lower() not in valid:
            raise ValueError(f"channel must be one of {valid}, got '{v}'")
        return v.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is not None and "@" not in v:
            raise ValueError(f"invalid email format: '{v}'")
        return v


class GetCustomerHistoryInput(BaseModel):
    email: str | None = Field(default=None, description="Customer email.")
    phone: str | None = Field(default=None, description="Customer phone.")
    customer_id: str | None = Field(default=None, description="Direct customer ID.")

    def has_identifier(self) -> bool:
        return bool(self.email or self.phone or self.customer_id)


class EscalateToHumanInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket to escalate.")
    team: str = Field(..., description="Target team name.")
    reason: str = Field(..., min_length=1, max_length=1000, description="Escalation reason.")
    priority: str = Field(default="P2", description="Priority: P1, P2, P3, P4.")
    customer_name: str | None = Field(default=None, description="Customer name.")
    summary: str | None = Field(default=None, max_length=5000, description="Issue summary.")

    @field_validator("team")
    @classmethod
    def validate_team(cls, v):
        valid = {t.value for t in EscalationTeam}
        if v not in valid:
            raise ValueError(f"team must be one of {valid}, got '{v}'")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        valid = {p.value for p in Priority}
        if v not in valid:
            raise ValueError(f"priority must be one of {valid}, got '{v}'")
        return v


class SendResponseInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket to respond to.")
    response_text: str = Field(..., min_length=1, max_length=10000, description="Response content.")
    channel: str = Field(..., description="Channel: email, whatsapp, web_form.")
    agent_name: str = Field(default="TaskFlow AI Agent", max_length=200, description="Agent name.")
    include_escalation_note: bool = Field(default=False, description="Append escalation note.")
    escalation_team: str | None = Field(default=None, description="Team for escalation note.")
    escalation_sla: str | None = Field(default=None, description="SLA for escalation note.")

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v):
        valid = {c.value for c in Channel}
        if v.lower() not in valid:
            raise ValueError(f"channel must be one of {valid}, got '{v}'")
        return v.lower()


# ============================================================
# IN-MEMORY STORES (for tool-level operations & tests)
# ============================================================

_customer_store: dict = {}
_ticket_store: dict = {}
_escalation_store: dict = {}
_conversation_store: dict = {}


def _resolve_customer(email: str | None = None, phone: str | None = None) -> str:
    for cid, profile in _customer_store.items():
        if email and profile.get("email") and profile["email"].lower() == email.lower():
            return cid
        if phone and profile.get("phone") == phone:
            return cid
    cid = generate_customer_id()
    _customer_store[cid] = {
        "customer_id": cid, "email": email, "phone": phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channels": [], "ticket_count": 0,
    }
    return cid


def _record_turn(customer_id: str, channel: str, topic: str, sentiment: str):
    _conversation_store.setdefault(customer_id, []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel, "topic": topic, "sentiment": sentiment,
    })
    profile = _customer_store.get(customer_id, {})
    if channel not in profile.get("channels", []):
        profile.setdefault("channels", []).append(channel)
    profile["ticket_count"] = profile.get("ticket_count", 0) + 1


# ============================================================
# KNOWLEDGE BASE (in-memory — fast lookup)
# ============================================================

_KB = {
    "password_reset": {
        "keywords": ["password", "reset", "forgot password", "login", "sign in", "can't log in", "cannot log in", "locked out", "access my account", "reset link", "expired", "not received", "didn't receive"],
        "content": {"overview": "Login page -> Forgot Password? -> enter email -> reset link (1 hour) -> new password (8+ chars, 1 upper, 1 number, 1 special).", "common_issues": ["Email not received: check spam, verify email, wait 5 min.", "Link expired: request new one.", "Account locked after 10 failed attempts."], "support_actions": ["Manually trigger reset email if delay > 10 min.", "Escalate if account compromised."]},
    },
    "create_project": {
        "keywords": ["create project", "new project", "add project", "+ new project", "can't create", "project limit", "can't find", "where is", "start a project"],
        "content": {"overview": "Log in -> '+ New Project' (top right) -> fill details -> Create.", "tier_limits": {"Free": "3 projects, 5 members", "Starter": "Unlimited, 50 members", "Professional": "Unlimited, 200 members", "Enterprise": "Unlimited, unlimited members"}, "common_issues": ["Limit reached: upgrade or archive.", "Button not visible: refresh/clear cache."]},
    },
    "invite_team_members": {
        "keywords": ["invite", "team member", "add member", "add user", "send invite", "invitation", "didn't receive", "not received", "bulk import", "role", "admin", "member", "viewer", "change role", "invite limit"],
        "content": {"overview": "Project -> Team tab -> Invite Members -> emails -> role -> Send.", "tier_limits": {"Free": "5", "Starter": "50", "Professional": "200", "Enterprise": "unlimited"}, "bulk_import": "Professional+. CSV: email,name,role. Max 500.", "common_issues": ["Check spam folder.", "Invites expire in 7 days.", "Role change: Team tab -> dropdown -> new role."]},
    },
    "kanban_board": {
        "keywords": ["kanban", "board", "drag", "drop", "column", "card", "slow", "loading", "not visible", "disappeared", "missing", "export", "pdf", "custom column", "add column", "WIP limit", "filter", "shortcut"],
        "content": {"overview": "Default view: Backlog, To Do, In Progress, In Review, Done.", "customization": ["Settings -> Manage Columns.", "WIP limits: Professional+."], "common_issues": ["Not draggable: check browser/extensions.", "Slow: use filters.", "Missing: check filters/archived."], "shortcuts": {"N": "New task", "F": "Filter", "/": "Search"}},
    },
    "pricing": {
        "keywords": ["pricing", "plan", "tier", "upgrade", "downgrade", "cost", "billing", "charge", "refund", "subscription", "free trial", "trial expired", "enterprise", "SSO", "on-premise", "nonprofit", "discount", "switch", "cancel"],
        "content": {"tiers": {"Free": "$0 — 5 members, 3 projects", "Starter": "$12/user/mo — 50 members, time tracking", "Professional": "$25/user/mo — 200 members, API, bulk import", "Enterprise": "Custom — SSO, on-premise, 99.99% SLA"}, "billing": ["Annual saves 20%.", "14-day free trial.", "30-day money-back.", "Nonprofit: 50% off.", "Downgrade: data preserved."]},
    },
}

_TEAMS = {
    "security": {"team": "Security Team", "email": "security@techcorp.com", "sla": "30 minutes"},
    "engineering": {"team": "Engineering Team", "email": "eng-support@techcorp.internal", "sla": "1 hour"},
    "billing": {"team": "Billing Team", "email": "billing@techcorp.com", "sla": "1 hour"},
    "sales": {"team": "Sales Team", "email": "sales@techcorp.com", "sla": "2 hours"},
    "support": {"team": "Support Team", "email": "support@techcorp.com", "sla": "1 hour"},
    "customer_success": {"team": "Customer Success", "email": "csm@techcorp.com", "sla": "1 hour"},
}


# ============================================================
# TOOL 1: search_knowledge_base
# ============================================================

@function_tool
def search_knowledge_base(input: SearchKnowledgeBaseInput) -> str:
    """Search the TaskFlow knowledge base for product documentation."""
    try:
        logger.info("Calling MCP: search_knowledge_base with query: %s", input.query)
        return _mcp_search_kb(query=input.query, topic=input.topic)
    except Exception as exc:
        logger.error("search_knowledge_base failed: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"Search failed: {exc}"}, indent=2)


# ============================================================
# TOOL 2: create_ticket
# ============================================================

@function_tool
def create_ticket(input: CreateTicketInput) -> str:
    """Create a new support ticket."""
    logger.info(f"DEBUG: create_ticket type is {type(create_ticket)}")
    try:
        logger.info("Calling MCP: create_ticket for %s", input.customer_name)
        return _mcp_create_ticket(
            customer_name=input.customer_name,
            message=input.message,
            channel=input.channel,
            email=input.email,
            phone=input.phone,
            subject=input.subject
        )
    except Exception as exc:
        logger.error("create_ticket failed: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"Ticket creation failed: {exc}"}, indent=2)


# ============================================================
# TOOL 3: get_customer_history
# ============================================================

@function_tool
def get_customer_history(input: GetCustomerHistoryInput) -> str:
    """Retrieve customer profile and conversation history."""
    try:
        logger.info("Calling MCP: get_customer_history")
        return _mcp_get_customer_history(
            email=input.email,
            phone=input.phone,
            customer_id=input.customer_id
        )
    except Exception as exc:
        logger.error("get_customer_history failed: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"History retrieval failed: {exc}"}, indent=2)


# ============================================================
# TOOL 4: escalate_to_human
# ============================================================

@function_tool
def escalate_to_human(input: EscalateToHumanInput) -> str:
    """Escalate a ticket to a human support team."""
    try:
        logger.info("Calling MCP: escalate_to_human for ticket %s", input.ticket_id)
        return _mcp_escalate_to_human(
            ticket_id=input.ticket_id,
            team=input.team,
            reason=input.reason,
            priority=input.priority,
            customer_name=input.customer_name,
            summary=input.summary
        )
    except Exception as exc:
        logger.error("escalate_to_human failed: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"Escalation failed: {exc}"}, indent=2)


# ============================================================
# TOOL 5: send_response
# ============================================================

@function_tool
def send_response(input: SendResponseInput) -> str:
    """Send a channel-formatted response to a customer."""
    try:
        logger.info("Calling MCP: send_response for ticket %s", input.ticket_id)
        return _mcp_send_response(
            ticket_id=input.ticket_id,
            response_text=input.response_text,
            channel=input.channel,
            agent_name=input.agent_name,
            include_escalation_note=input.include_escalation_note,
            escalation_team=input.escalation_team,
            escalation_sla=input.escalation_sla
        )
    except Exception as exc:
        logger.error("send_response failed: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"Response delivery failed: {exc}"}, indent=2)
