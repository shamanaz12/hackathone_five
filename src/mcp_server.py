"""
TaskFlow MCP Server
CRM Digital FTE Factory Final Hackathon 5

Exposes 5 tools via the Model Context Protocol (MCP):
  - search_knowledge_base
  - create_ticket
  - get_customer_history
  - escalate_to_human
  - send_response

Connected to Local SQLite Database.
"""

import re
import json
import sys
import io
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from mcp.server.fastmcp import FastMCP

from production.database.session import get_session_factory
from production.database.models import (
    Customer,
    Ticket,
    Conversation,
    Message,
    Escalation,
    KnowledgeBase,
)
from production.database.repositories import (
    CustomerRepository,
    TicketRepository,
    ConversationRepository,
    MessageRepository,
    EscalationRepository,
    KnowledgeBaseRepository,
)

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
    """Search the TaskFlow knowledge base for relevant information."""
    session_factory = get_session_factory()
    with session_factory() as session:
        repo = KnowledgeBaseRepository(session)
        
        if topic:
            kb = repo.find_by_topic(topic)
            # If topic provided, verify query relevance (simple keyword check)
            if kb:
                query_lower = query.lower()
                matches = any(kw.lower() in query_lower for kw in (kb.keywords or []))
                matches = matches or any(kw.lower() in kb.title.lower() for kw in query_lower.split())
                results = [kb] if matches else []
            else:
                results = []
        else:
            results = repo.search(query)

        if not results:
            return json.dumps({
                "status": "not_found",
                "message": "No matching content found.",
            }, indent=2)

        formatted_results = []
        for kb in results:
            formatted_results.append({
                "topic": kb.topic,
                "title": kb.title,
                "content": kb.overview,
                "details": kb.content
            })

        return json.dumps({
            "status": "found",
            "results_count": len(formatted_results),
            "results": formatted_results,
        }, indent=2)


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
    """Create a new support ticket in the TaskFlow system."""
    session_factory = get_session_factory()
    with session_factory() as session:
        cust_repo = CustomerRepository(session)
        ticket_repo = TicketRepository(session)
        conv_repo = ConversationRepository(session)

        # 1. Resolve or Create Customer
        customer = cust_repo.resolve_or_create(
            name=customer_name,
            email=email,
            phone=phone
        )

        # 2. Create Ticket
        ticket = ticket_repo.create(
            customer_id=customer.customer_id,
            channel=channel,
            message=message,
            subject=subject
        )

        # 3. Create Conversation Turn
        conv_repo.create_turn(
            customer_id=customer.customer_id,
            channel=channel,
            ticket_id=ticket.ticket_id
        )

        return json.dumps({
            "status": "created",
            "ticket": ticket.to_dict(),
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
    """Retrieve the full conversation history and profile for a customer."""
    if not any([email, phone, customer_id]):
        return json.dumps({"status": "error", "message": "At least one identifier (email, phone, or customer_id) must be provided"}, indent=2)

    session_factory = get_session_factory()
    with session_factory() as session:
        cust_repo = CustomerRepository(session)
        
        customer = None
        if customer_id:
            customer = cust_repo.find_by_id(customer_id)
        elif email:
            customer = cust_repo.find_by_email(email)
        elif phone:
            customer = cust_repo.find_by_phone(phone)

        if not customer:
            return json.dumps({"status": "not_found", "message": "Customer not found"}, indent=2)

        # Fetch related tickets and conversations manually or via relationships
        tickets = [t.to_dict() for t in customer.tickets]
        
        return json.dumps({
            "status": "found",
            "customer_profile": customer.to_dict(),
            "tickets": tickets,
            "total_tickets": len(tickets),
            "total_interactions": len(customer.conversations)
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
    """Escalate a support ticket to a human support team."""
    if team not in ESCALATION_TEAMS:
        return json.dumps({"status": "error", "message": f"Invalid team: {team}"}, indent=2)

    session_factory = get_session_factory()
    with session_factory() as session:
        ticket_repo = TicketRepository(session)
        esc_repo = EscalationRepository(session)

        ticket = ticket_repo.find_by_id(ticket_id)
        if not ticket:
            return json.dumps({"status": "error", "message": "Ticket not found"}, indent=2)

        team_info = ESCALATION_TEAMS[team]
        
        escalation = esc_repo.create(
            ticket_id=ticket_id,
            customer_id=ticket.customer_id,
            team=team_info["team"],
            reason=reason,
            sla=team_info["sla"],
            priority=priority,
            summary=summary
        )

        ticket_repo.update_status(ticket_id, "escalated")

        return json.dumps({
            "status": "escalated",
            "escalation": escalation.to_dict(),
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
    """Send a support response to a customer."""
    session_factory = get_session_factory()
    with session_factory() as session:
        ticket_repo = TicketRepository(session)
        msg_repo = MessageRepository(session)
        conv_repo = ConversationRepository(session)

        ticket = ticket_repo.find_by_id(ticket_id)
        if not ticket:
            return json.dumps({"status": "error", "message": "Ticket not found"}, indent=2)

        # Get or create turn
        last_turn = conv_repo.get_last_turn(ticket.customer_id)
        if not last_turn:
            last_turn = conv_repo.create_turn(ticket.customer_id, channel, ticket_id)

        # Apply escalation note if requested
        final_text = response_text
        if include_escalation_note and escalation_team and escalation_sla:
            final_text += f"\n\n[Escalation Note]: This ticket has been escalated to {escalation_team}. Expected response within {escalation_sla}."

        # Create message record
        msg_repo.create(
            conversation_id=last_turn.conversation_id,
            ticket_id=ticket_id,
            role="agent",
            content=final_text,
            channel=channel,
            agent_name=agent_name
        )

        ticket_repo.update_status(ticket_id, "responded")

        return json.dumps({
            "status": "sent",
            "ticket_id": ticket_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, indent=2)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("Starting TaskFlow MCP Server (SQLite Mode)...")
    mcp.run()
