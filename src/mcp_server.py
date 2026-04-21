"""
TaskFlow MCP Server
CRM Digital FTE Factory Final Hackathon 5

Exposes 5 tools via the Model Context Protocol (MCP):
  - search_knowledge_base
  - create_ticket
  - get_customer_history
  - escalate_to_human
  - send_response

Usage:
  python src/mcp_server.py
"""

import re
import json
import sys
import io
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from mcp.server.fastmcp import FastMCP

# Force UTF-8 for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ============================================================
# CHANNEL ENUM
# ============================================================

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# ============================================================
# EMBEDDED KNOWLEDGE BASE
# ============================================================

KNOWLEDGE_BASE = {
    "password_reset": {
        "keywords": [
            "password", "reset", "forgot password", "login", "sign in",
            "can't log in", "cannot log in", "locked out", "access my account",
            "reset link", "expired", "not received", "didn't receive"
        ],
        "content": {
            "overview": (
                "Users reset passwords via the login page -> 'Forgot Password?' -> "
                "enter email -> receive reset link (valid 1 hour) -> set new password."
            ),
            "requirements": "8+ characters, 1 uppercase, 1 number, 1 special character.",
            "common_issues": [
                "Reset email not received: check spam, verify email, wait 5 min, resend available.",
                "Reset link expired: link valid for 1 hour, request a new one.",
                "Email not found: verify email matches registration, check typos.",
                "Password doesn't meet requirements: must satisfy all complexity rules.",
            ],
            "security_notes": [
                "Max 5 failed reset attempts per hour.",
                "Account locked after 10 failed attempts.",
                "All password changes trigger a notification email.",
            ],
            "support_actions": [
                "Verify account status in admin dashboard.",
                "Manually trigger reset email if delay > 10 minutes.",
                "Escalate if user suspects account compromise.",
            ],
        },
    },
    "create_project": {
        "keywords": [
            "create project", "new project", "add project", "+ new project",
            "can't create", "project limit", "can't find", "where is",
            "start a project", "make a project"
        ],
        "content": {
            "overview": (
                "Log in -> click '+ New Project' (top right) -> fill details -> Create Project."
            ),
            "fields": "Project Name (required, 100 chars), Description (optional, 5000 chars), Template, Visibility, Dates.",
            "tier_limits": {
                "Free": "3 projects, 5 members",
                "Starter": "Unlimited projects, 50 members",
                "Professional": "Unlimited projects, 200 members",
                "Enterprise": "Unlimited projects, unlimited members",
            },
            "common_issues": [
                "Project limit reached: upgrade tier or archive old projects.",
                "Can't add members: check tier limits, ensure invitees have accounts.",
                "Template not loading: refresh, try blank project, clear cache.",
                "Project not visible: check visibility settings, verify workspace.",
            ],
        },
    },
    "invite_team_members": {
        "keywords": [
            "invite", "team member", "add member", "add user", "send invite",
            "invitation", "didn't receive", "not received", "bulk import",
            "role", "admin", "member", "viewer", "change role",
            "invite limit", "member limit"
        ],
        "content": {
            "overview": (
                "Open project -> Team tab -> Invite Members -> enter emails -> "
                "select role (Admin/Member/Viewer) -> Send Invites."
            ),
            "invitation_flow": (
                "Invitee receives email -> if has account, added immediately; "
                "if not, prompted to sign up (free) -> then added. "
                "Invitation expires after 7 days."
            ),
            "tier_limits": {
                "Free": "5 members",
                "Starter": "50 members",
                "Professional": "200 members",
                "Enterprise": "unlimited members",
            },
            "bulk_import": "Professional+ only. CSV with columns: email, name, role. Max 500 per upload.",
            "common_issues": [
                "Invitee didn't receive: check spam, verify email, resend, check if already registered.",
                "Invite limit reached: check tier limits, upgrade if needed.",
                "Wrong role: Admin can change role in Team settings.",
                "Can't find Invite button: only Admins and Members can invite; Viewers cannot.",
            ],
        },
    },
    "kanban_board": {
        "keywords": [
            "kanban", "board", "drag", "drop", "column", "card",
            "slow", "loading", "not visible", "disappeared", "missing",
            "export", "pdf", "custom column", "add column",
            "WIP limit", "filter", "shortcut"
        ],
        "content": {
            "overview": (
                "Default project view. Columns: Backlog, To Do, In Progress, In Review, Done."
            ),
            "customization": [
                "Add/Remove/Rename columns: Settings -> Manage Columns.",
                "Reorder columns: drag and drop headers.",
                "WIP limits per column: Professional+ tier.",
            ],
            "card_info": "Title, assignee avatar, due date (color-coded), priority, labels, attachments, comments.",
            "keyboard_shortcuts": {
                "N": "Create new task",
                "F": "Open filter menu",
                "/": "Focus search bar",
                "Left/Right": "Move card between columns",
                "Delete": "Archive selected card",
            },
            "common_issues": [
                "Cards not draggable: check browser, disable extensions, refresh.",
                "Column not showing cards: check WIP limits, verify task status.",
                "Slow loading: large boards take time, use filters.",
                "Missing cards: check filters, verify not archived/deleted.",
            ],
        },
    },
    "pricing": {
        "keywords": [
            "pricing", "plan", "tier", "upgrade", "downgrade", "cost",
            "billing", "charge", "refund", "subscription",
            "free trial", "trial expired", "enterprise", "SSO",
            "on-premise", "nonprofit", "discount", "switch", "cancel"
        ],
        "content": {
            "tiers": {
                "Free": "$0/mo -- 5 members, 3 projects, basic Kanban, 1 GB storage.",
                "Starter": "$12/user/mo -- unlimited projects, 50 members, time tracking, integrations, 50 GB, priority support.",
                "Professional": "$25/user/mo -- 200 members, custom workflows, API, advanced reporting, bulk import, 200 GB.",
                "Enterprise": "Custom pricing -- unlimited, SSO/SAML, on-premise, dedicated support, 99.99% SLA.",
            },
            "billing": [
                "Monthly or annual (save 20% on annual).",
                "14-day free trial for Starter/Professional (no credit card).",
                "30-day money-back guarantee.",
                "Upgrade/downgrade anytime, prorated billing.",
                "Nonprofit discount: 50% off all paid tiers.",
                "Cancel anytime, no fees, data exportable for 30 days.",
                "Downgrade: data preserved, features revert at next billing cycle.",
            ],
        },
    },
}

# ============================================================
# ESCALATION CONFIG
# ============================================================

ESCALATION_TEAMS = {
    "security": {
        "team": "Security Team",
        "email": "security@techcorp.com",
        "sla": "30 minutes",
        "priority": "P1",
    },
    "engineering": {
        "team": "Engineering Team",
        "email": "eng-support@techcorp.internal",
        "sla": "1 hour",
        "priority": "P2",
    },
    "billing": {
        "team": "Billing Team",
        "email": "billing@techcorp.com",
        "sla": "1 hour",
        "priority": "P2",
    },
    "sales": {
        "team": "Sales Team",
        "email": "sales@techcorp.com",
        "sla": "2 hours",
        "priority": "P2",
    },
    "support": {
        "team": "Support Team",
        "email": "support@techcorp.com",
        "sla": "1 hour",
        "priority": "P2",
    },
    "customer_success": {
        "team": "Customer Success",
        "email": "csm@techcorp.com",
        "sla": "1 hour",
        "priority": "P2",
    },
}

# ============================================================
# IN-MEMORY STORES (simulated DB)
# ============================================================

# customer_id -> profile
_customer_store: dict = {}
# ticket_id -> ticket
_ticket_store: dict = {}
# escalation_id -> escalation
_escalation_store: dict = {}
# conversation turns: customer_id -> list
_conversation_store: dict = {}

_counter = {"ticket": 0, "escalation": 0, "customer": 0}


def _next_id(prefix: str) -> str:
    _counter[prefix] += 1
    return f"{prefix.upper()}-{_counter[prefix]:04d}"


def _resolve_customer(email: Optional[str] = None, phone: Optional[str] = None) -> str:
    """Resolve or create a customer ID from email/phone."""
    for cid, profile in _customer_store.items():
        if email and profile.get("email") and profile["email"].lower() == email.lower():
            return cid
        if phone and profile.get("phone") == phone:
            return cid
    cid = _next_id("customer")
    _customer_store[cid] = {
        "customer_id": cid,
        "email": email,
        "phone": phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channels": [],
        "ticket_count": 0,
    }
    return cid


def _record_turn(customer_id: str, channel: str, topic: str, sentiment: str):
    if customer_id not in _conversation_store:
        _conversation_store[customer_id] = []
    _conversation_store[customer_id].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "topic": topic,
        "sentiment": sentiment,
    })
    profile = _customer_store.get(customer_id, {})
    if channel not in profile.get("channels", []):
        profile.setdefault("channels", []).append(channel)
    profile["ticket_count"] = profile.get("ticket_count", 0) + 1


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP(
    "TaskFlow Support Agent",
    instructions=(
        "TaskFlow AI Support Agent for TechCorp. "
        "Use these tools to search the knowledge base, manage tickets, "
        "view customer history, escalate to human agents, and send responses."
    ),
)


# ---------------------------------------------------------------
# TOOL 1: search_knowledge_base
# ---------------------------------------------------------------

@mcp.tool()
def search_knowledge_base(
    query: str,
    topic: Optional[str] = None,
) -> str:
    """Search the TaskFlow knowledge base for relevant information.

    Args:
        query: The customer's question or issue description.
        topic: Optional topic filter. One of: password_reset, create_project,
               invite_team_members, kanban_board, pricing.

    Returns:
        Matching knowledge base content as formatted text.
    """
    query_lower = query.lower()
    results = []

    # If topic is specified, search only that section
    if topic:
        if topic in KNOWLEDGE_BASE:
            kb = KNOWLEDGE_BASE[topic]
            score = sum(1 for kw in kb["keywords"] if kw in query_lower)
            if score > 0:
                results.append({
                    "topic": topic,
                    "relevance_score": score,
                    "content": kb["content"],
                })
        if not results:
            return json.dumps({
                "status": "not_found",
                "message": f"No matching content found for topic '{topic}'.",
            }, indent=2)
    else:
        # Search all sections, rank by keyword overlap
        for topic_name, kb in KNOWLEDGE_BASE.items():
            score = sum(1 for kw in kb["keywords"] if kw in query_lower)
            if score > 0:
                results.append({
                    "topic": topic_name,
                    "relevance_score": score,
                    "content": kb["content"],
                })

    if not results:
        return json.dumps({
            "status": "not_found",
            "message": "No matching content found. Consider escalating to a human agent.",
        }, indent=2)

    # Sort by relevance
    results.sort(key=lambda r: r["relevance_score"], reverse=True)

    output = {
        "status": "found",
        "results_count": len(results),
        "results": results,
    }
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------
# TOOL 2: create_ticket
# ---------------------------------------------------------------

@mcp.tool()
def create_ticket(
    customer_name: str,
    message: str,
    channel: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Create a new support ticket in the TaskFlow system.

    Args:
        customer_name: Full name of the customer.
        message: The customer's support message.
        channel: Communication channel. Must be one of: email, whatsapp, web_form.
        email: Customer's email address (optional).
        phone: Customer's phone number (optional).
        subject: Ticket subject line (optional, used for email/web_form).

    Returns:
        Created ticket details including ticket_id, customer_id, and timestamp.
    """
    # Validate channel
    try:
        channel_enum = Channel(channel.lower())
    except ValueError:
        return json.dumps({
            "status": "error",
            "message": f"Invalid channel '{channel}'. Must be one of: {', '.join(c.value for c in Channel)}",
        }, indent=2)

    ticket_id = _next_id("ticket")
    customer_id = _resolve_customer(email, phone)
    now = datetime.now(timezone.utc).isoformat()

    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "email": email,
        "phone": phone,
        "channel": channel_enum.value,
        "subject": subject,
        "message": message,
        "status": "open",
        "priority": "P3",
        "created_at": now,
        "updated_at": now,
    }

    _ticket_store[ticket_id] = ticket
    _record_turn(customer_id, channel_enum.value, "general", "neutral")

    return json.dumps({
        "status": "created",
        "ticket": ticket,
    }, indent=2)


# ---------------------------------------------------------------
# TOOL 3: get_customer_history
# ---------------------------------------------------------------

@mcp.tool()
def get_customer_history(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> str:
    """Retrieve the full conversation history and profile for a customer.

    At least one of email, phone, or customer_id must be provided.

    Args:
        email: Customer's email address.
        phone: Customer's phone number.
        customer_id: Direct customer ID (e.g., CUSTOMER-0001).

    Returns:
        Customer profile and conversation history.
    """
    # Resolve customer
    cid = customer_id
    if not cid:
        cid = _resolve_customer(email, phone)
        if not cid or cid not in _customer_store:
            return json.dumps({
                "status": "not_found",
                "message": "No customer found with the provided identifiers.",
            }, indent=2)

    profile = _customer_store.get(cid, {})
    conversations = _conversation_store.get(cid, [])
    tickets = [
        t for t in _ticket_store.values()
        if t.get("customer_id") == cid
    ]

    return json.dumps({
        "status": "found",
        "customer_profile": profile,
        "conversation_history": conversations,
        "tickets": tickets,
        "total_interactions": len(conversations),
        "total_tickets": len(tickets),
    }, indent=2)


# ---------------------------------------------------------------
# TOOL 4: escalate_to_human
# ---------------------------------------------------------------

@mcp.tool()
def escalate_to_human(
    ticket_id: str,
    team: str,
    reason: str,
    priority: str = "P2",
    customer_name: Optional[str] = None,
    summary: Optional[str] = None,
) -> str:
    """Escalate a support ticket to a human support team.

    Args:
        ticket_id: The ticket to escalate (e.g., TICKET-0001).
        team: Target team. One of: security, engineering, billing, sales, support, customer_success.
        reason: Reason for escalation.
        priority: Ticket priority. One of: P1, P2, P3, P4. Defaults to P2.
        customer_name: Customer name for the escalation record.
        summary: Brief summary of the issue and steps already taken.

    Returns:
        Escalation record with team details, SLA, and escalation_id.
    """
    # Validate ticket exists
    if ticket_id not in _ticket_store:
        return json.dumps({
            "status": "error",
            "message": f"Ticket '{ticket_id}' not found. Create it first with create_ticket.",
        }, indent=2)

    # Validate team
    if team not in ESCALATION_TEAMS:
        valid = ", ".join(ESCALATION_TEAMS.keys())
        return json.dumps({
            "status": "error",
            "message": f"Invalid team '{team}'. Must be one of: {valid}",
        }, indent=2)

    escalation_id = _next_id("escalation")
    team_info = ESCALATION_TEAMS[team]
    now = datetime.now(timezone.utc).isoformat()

    ticket = _ticket_store[ticket_id]
    ticket["status"] = "escalated"
    ticket["updated_at"] = now

    escalation = {
        "escalation_id": escalation_id,
        "ticket_id": ticket_id,
        "customer_id": ticket.get("customer_id"),
        "customer_name": customer_name or ticket.get("customer_name", "Unknown"),
        "team": team_info["team"],
        "team_email": team_info["email"],
        "sla": team_info["sla"],
        "priority": priority,
        "reason": reason,
        "summary": summary,
        "status": "pending",
        "created_at": now,
    }

    _escalation_store[escalation_id] = escalation

    return json.dumps({
        "status": "escalated",
        "escalation": escalation,
    }, indent=2)


# ---------------------------------------------------------------
# TOOL 5: send_response
# ---------------------------------------------------------------

@mcp.tool()
def send_response(
    ticket_id: str,
    response_text: str,
    channel: str,
    agent_name: str = "TaskFlow AI Agent",
    include_escalation_note: bool = False,
    escalation_team: Optional[str] = None,
    escalation_sla: Optional[str] = None,
) -> str:
    """Send a support response to a customer via their preferred channel.

    Args:
        ticket_id: The ticket to respond to.
        response_text: The response message content.
        channel: Channel to send via. Must be one of: email, whatsapp, web_form.
        agent_name: Name of the responding agent. Defaults to 'TaskFlow AI Agent'.
        include_escalation_note: Whether to append an escalation notification.
        escalation_team: Team name to mention in escalation note.
        escalation_sla: SLA timeframe to mention in escalation note.

    Returns:
        Confirmation of response delivery with timestamp and channel formatting applied.
    """
    # Validate ticket
    if ticket_id not in _ticket_store:
        return json.dumps({
            "status": "error",
            "message": f"Ticket '{ticket_id}' not found.",
        }, indent=2)

    # Validate channel
    try:
        channel_enum = Channel(channel.lower())
    except ValueError:
        return json.dumps({
            "status": "error",
            "message": f"Invalid channel '{channel}'. Must be one of: {', '.join(c.value for c in Channel)}",
        }, indent=2)

    ticket = _ticket_store[ticket_id]
    now = datetime.now(timezone.utc).isoformat()

    # Apply channel-specific formatting
    formatted_text = _format_for_channel(response_text, channel_enum.value)

    # Append escalation note if requested
    if include_escalation_note and escalation_team and escalation_sla:
        formatted_text += (
            f"\n\n---\n"
            f"I've also escalated this issue to our {escalation_team}. "
            f"You can expect a response within {escalation_sla}."
        )

    # Update ticket
    ticket["status"] = "responded" if ticket["status"] != "escalated" else "escalated"
    ticket["updated_at"] = now
    ticket["last_response"] = {
        "agent": agent_name,
        "text": response_text,
        "formatted_text": formatted_text,
        "channel": channel_enum.value,
        "timestamp": now,
    }

    return json.dumps({
        "status": "sent",
        "ticket_id": ticket_id,
        "channel": channel_enum.value,
        "agent": agent_name,
        "timestamp": now,
        "response_preview": formatted_text[:200] + ("..." if len(formatted_text) > 200 else ""),
    }, indent=2)


# ============================================================
# CHANNEL FORMATTER
# ============================================================

def _format_for_channel(text: str, channel: str) -> str:
    """Apply channel-specific formatting to response text."""
    if channel == Channel.WHATSAPP.value:
        # Shorten long responses, use emoji-friendly formatting
        lines = text.split("\n")
        formatted = []
        for line in lines:
            # Replace markdown bullets with emoji
            line = re.sub(r'^[-*]\s', '\u2022 ', line)
            # Replace numbered steps with emoji numbers
            match = re.match(r'^(\d+)\.\s', line)
            if match:
                num = match.group(1)
                line = re.sub(r'^\d+\.\s', f'[{num}] ', line)
            formatted.append(line)
        result = "\n".join(formatted)
        # Truncate if very long (WhatsApp preference for brevity)
        if len(result) > 1000:
            result = result[:1000] + "\n\n[Message truncated -- full details sent via email]"
        return result

    elif channel == Channel.EMAIL.value:
        # Full formatting, professional
        return text

    elif channel == Channel.WEB_FORM.value:
        # Structured, medium length
        return text

    return text


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("Starting TaskFlow MCP Server...")
    print("Available tools:")
    print("  1. search_knowledge_base  - Search product documentation")
    print("  2. create_ticket          - Create a new support ticket")
    print("  3. get_customer_history   - Retrieve customer conversation history")
    print("  4. escalate_to_human      - Escalate a ticket to a human team")
    print("  5. send_response          - Send a response to a customer")
    print()
    mcp.run()
