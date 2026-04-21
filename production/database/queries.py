"""
TaskFlow AI Support Agent — Database Query Helpers
CRM Digital FTE Factory Final Hackathon 5

Provides async SQLAlchemy query helpers for:
- Customer resolution (find/create by email/phone)
- Conversation management (record turns, get history)
- Ticket operations (create, update, escalate, search)
- Escalation management
- Metrics and reporting
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


# ============================================================
# CUSTOMER QUERIES
# ============================================================

async def resolve_customer_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[dict]:
    """
    Find a customer by email address (case-insensitive).

    Args:
        db: Async SQLAlchemy session.
        email: Customer email address.

    Returns:
        Customer dict or None if not found.
    """
    from production.database.models import Customer

    stmt = select(Customer).where(func.lower(Customer.email) == email.lower())
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer:
        return customer.to_dict()
    return None


async def resolve_customer_by_phone(
    db: AsyncSession,
    phone: str,
) -> Optional[dict]:
    """
    Find a customer by phone number.

    Args:
        db: Async SQLAlchemy session.
        phone: Customer phone number.

    Returns:
        Customer dict or None if not found.
    """
    from production.database.models import Customer

    stmt = select(Customer).where(Customer.phone == phone)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer:
        return customer.to_dict()
    return None


async def resolve_or_create_customer(
    db: AsyncSession,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: str = "Unknown",
    defaults: Optional[dict] = None,
) -> dict:
    """
    Find existing customer by email or phone, or create a new one.

    This is the primary identity resolution function used by the agent pipeline.

    Args:
        db: Async SQLAlchemy session.
        email: Customer email address.
        phone: Customer phone number.
        name: Customer name (used if creating new).
        defaults: Additional fields for new customer creation.

    Returns:
        Customer dict (existing or newly created).
    """
    from production.database.models import Customer

    # Try email first
    if email:
        existing = await resolve_customer_by_email(db, email)
        if existing:
            return existing

    # Try phone
    if phone:
        existing = await resolve_customer_by_phone(db, phone)
        if existing:
            return existing

    # Create new customer
    now = datetime.now(timezone.utc)
    customer_data = {
        "name": name,
        "email": email,
        "phone": phone,
        "tier": "unknown",
        "channels_seen": [],
        "total_tickets": 0,
        "resolved_tickets": 0,
        "escalated_tickets": 0,
        "sentiment_history": [],
        "topic_history": [],
        "last_contact": now,
        "created_at": now,
        "updated_at": now,
    }
    if defaults:
        customer_data.update(defaults)

    new_customer = Customer(**customer_data)
    db.add(new_customer)
    await db.commit()
    await db.refresh(new_customer)

    logger.info("Created new customer: %s (%s)", name, new_customer.customer_id)
    return new_customer.to_dict()


async def update_customer_channels(
    db: AsyncSession,
    customer_id: str,
    channel: str,
) -> bool:
    """
    Add a channel to a customer's channels_seen array if not already present.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        channel: Channel name (email, whatsapp, web_form).

    Returns:
        True if updated, False if channel already present.
    """
    from production.database.models import Customer

    stmt = select(Customer).where(Customer.customer_id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        return False

    if channel not in customer.channels_seen:
        customer.channels_seen.append(channel)
        customer.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("Added channel '%s' to customer %s", channel, customer_id)
        return True
    return False


async def update_customer_sentiment(
    db: AsyncSession,
    customer_id: str,
    score: int,
    timestamp: Optional[str] = None,
) -> bool:
    """
    Append a sentiment score to a customer's sentiment history.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        score: Sentiment score (-2 to +2).
        timestamp: ISO timestamp (defaults to now).

    Returns:
        True if updated.
    """
    from production.database.models import Customer

    stmt = select(Customer).where(Customer.customer_id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        return False

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    customer.sentiment_history.append([ts, score])
    customer.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def get_customer_360(
    db: AsyncSession,
    customer_id: str,
) -> Optional[dict]:
    """
    Get a complete customer profile with ticket and conversation counts.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.

    Returns:
        Dict with profile, ticket stats, and recent activity.
    """
    from production.database.models import Customer, Ticket, Conversation

    stmt = (
        select(Customer)
        .options(selectinload(Customer.tickets), selectinload(Customer.conversations))
        .where(Customer.customer_id == customer_id)
    )
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        return None

    open_tickets = sum(1 for t in customer.tickets if t.status in ("open", "in_progress"))
    escalated_tickets = sum(1 for t in customer.tickets if t.status == "escalated")

    return {
        "profile": customer.to_dict(),
        "stats": {
            "total_tickets": len(customer.tickets),
            "open_tickets": open_tickets,
            "escalated_tickets": escalated_tickets,
            "total_conversations": len(customer.conversations),
            "avg_sentiment": (
                sum(s[1] for s in customer.sentiment_history) / len(customer.sentiment_history)
                if customer.sentiment_history else 0
            ),
        },
        "recent_tickets": [t.to_dict() for t in sorted(customer.tickets, key=lambda t: t.created_at, reverse=True)[:5]],
    }


# ============================================================
# TICKET QUERIES
# ============================================================

async def create_ticket(
    db: AsyncSession,
    customer_id: str,
    channel: str,
    message: str,
    subject: Optional[str] = None,
    priority: str = "P3",
    topic: Optional[str] = None,
    sentiment_score: int = 0,
    sentiment_label: str = "neutral",
    is_follow_up: bool = False,
    channel_switch: bool = False,
    previous_channel: Optional[str] = None,
) -> dict:
    """
    Create a new support ticket.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Associated customer ID.
        channel: Communication channel.
        message: Customer message content.
        subject: Optional subject line.
        priority: Ticket priority (P1-P4).
        topic: Classified topic.
        sentiment_score: Sentiment score (-2 to +2).
        sentiment_label: Sentiment label.
        is_follow_up: Whether this is a follow-up ticket.
        channel_switch: Whether customer switched channels.
        previous_channel: Previous channel name.

    Returns:
        Created ticket dict.
    """
    from production.database.models import Ticket

    now = datetime.now(timezone.utc)
    ticket = Ticket(
        customer_id=customer_id,
        channel=channel,
        subject=subject,
        message=message,
        status="open",
        priority=priority,
        topic=topic,
        sentiment_score=sentiment_score,
        sentiment_label=sentiment_label,
        ai_attempts=0,
        is_follow_up=is_follow_up,
        channel_switch=channel_switch,
        previous_channel=previous_channel,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)

    # Increment customer ticket count
    from production.database.models import Customer
    stmt = select(Customer).where(Customer.customer_id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()
    if customer:
        customer.total_tickets += 1
        customer.last_contact = now

    await db.commit()
    await db.refresh(ticket)

    logger.info("Created ticket %s for customer %s", ticket.ticket_id, customer_id)
    return ticket.to_dict()


async def get_ticket(
    db: AsyncSession,
    ticket_id: str,
) -> Optional[dict]:
    """Get a ticket by ID with customer and messages loaded."""
    from production.database.models import Ticket

    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.customer), selectinload(Ticket.messages))
        .where(Ticket.ticket_id == ticket_id)
    )
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        return ticket.to_dict()
    return None


async def update_ticket_status(
    db: AsyncSession,
    ticket_id: str,
    status: str,
    ai_attempts: Optional[int] = None,
) -> bool:
    """
    Update ticket status and optionally AI attempt count.

    Args:
        db: Async SQLAlchemy session.
        ticket_id: Ticket ID.
        status: New status (open, in_progress, responded, escalated, resolved, closed).
        ai_attempts: New AI attempt count.

    Returns:
        True if updated.
    """
    from production.database.models import Ticket

    stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        return False

    ticket.status = status
    ticket.updated_at = datetime.now(timezone.utc)
    if ai_attempts is not None:
        ticket.ai_attempts = ai_attempts
    if status in ("resolved", "closed"):
        ticket.resolved_at = datetime.now(timezone.utc)
    if status == "closed":
        ticket.closed_at = datetime.now(timezone.utc)

    await db.commit()
    return True


async def increment_ai_attempts(
    db: AsyncSession,
    ticket_id: str,
) -> int:
    """
    Increment the AI attempt counter for a ticket.

    Returns:
        New attempt count.
    """
    from production.database.models import Ticket

    stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        return 0

    ticket.ai_attempts += 1
    ticket.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return ticket.ai_attempts


async def search_tickets(
    db: AsyncSession,
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    channel: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Search tickets with optional filters.

    Returns:
        List of ticket dicts sorted by created_at descending.
    """
    from production.database.models import Ticket

    stmt = select(Ticket)
    conditions = []
    if customer_id:
        conditions.append(Ticket.customer_id == customer_id)
    if status:
        conditions.append(Ticket.status == status)
    if priority:
        conditions.append(Ticket.priority == priority)
    if channel:
        conditions.append(Ticket.channel == channel)
    if topic:
        conditions.append(Ticket.topic == topic)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(desc(Ticket.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    tickets = result.scalars().all()

    return [t.to_dict() for t in tickets]


async def get_active_tickets_by_priority(
    db: AsyncSession,
) -> dict[str, list[dict]]:
    """
    Get all active (open, in_progress, escalated) tickets grouped by priority.

    Returns:
        Dict with priority keys and ticket list values.
    """
    from production.database.models import Ticket

    stmt = (
        select(Ticket)
        .where(Ticket.status.in_(["open", "in_progress", "escalated"]))
        .order_by(
            func.case(
                (Ticket.priority == "P1", 1),
                (Ticket.priority == "P2", 2),
                (Ticket.priority == "P3", 3),
                (Ticket.priority == "P4", 4),
            ),
            Ticket.created_at,
        )
    )
    result = await db.execute(stmt)
    tickets = result.scalars().all()

    grouped: dict[str, list[dict]] = {"P1": [], "P2": [], "P3": [], "P4": []}
    for t in tickets:
        grouped.setdefault(t.priority, []).append(t.to_dict())
    return grouped


# ============================================================
# CONVERSATION QUERIES
# ============================================================

async def record_conversation_turn(
    db: AsyncSession,
    customer_id: str,
    ticket_id: Optional[str],
    channel: str,
    topic: Optional[str] = None,
    sentiment_score: int = 0,
    sentiment_label: str = "neutral",
    resolution_status: str = "new",
) -> dict:
    """
    Record a new conversation turn for a customer.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        ticket_id: Associated ticket ID (optional).
        channel: Communication channel.
        topic: Classified topic.
        sentiment_score: Sentiment score.
        sentiment_label: Sentiment label.
        resolution_status: Resolution status.

    Returns:
        Created conversation turn dict.
    """
    from production.database.models import Conversation

    # Auto-increment turn number
    stmt = select(func.coalesce(func.max(Conversation.turn_number), 0)).where(
        Conversation.customer_id == customer_id
    )
    result = await db.execute(stmt)
    next_turn = result.scalar() + 1

    turn = Conversation(
        customer_id=customer_id,
        ticket_id=ticket_id,
        turn_number=next_turn,
        channel=channel,
        topic=topic,
        sentiment_score=sentiment_score,
        sentiment_label=sentiment_label,
        resolution_status=resolution_status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    await db.commit()
    await db.refresh(turn)

    return turn.to_dict()


async def get_customer_conversations(
    db: AsyncSession,
    customer_id: str,
    limit: int = 20,
) -> list[dict]:
    """
    Get conversation history for a customer.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        limit: Max turns to return.

    Returns:
        List of conversation turn dicts sorted by turn_number.
    """
    from production.database.models import Conversation

    stmt = (
        select(Conversation)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.turn_number.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    turns = result.scalars().all()

    return [t.to_dict() for t in reversed(turns)]


async def get_last_conversation_turn(
    db: AsyncSession,
    customer_id: str,
) -> Optional[dict]:
    """Get the most recent conversation turn for a customer."""
    from production.database.models import Conversation

    stmt = (
        select(Conversation)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.turn_number.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    turn = result.scalar_one_or_none()

    if turn:
        return turn.to_dict()
    return None


async def detect_follow_up(
    db: AsyncSession,
    customer_id: str,
    new_topic: str,
) -> bool:
    """
    Check if the new topic matches the last conversation topic.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        new_topic: Topic of the new inquiry.

    Returns:
        True if this is a follow-up on the same topic.
    """
    last_turn = await get_last_conversation_turn(db, customer_id)
    if last_turn and last_turn.get("topic") == new_topic:
        return True
    return False


async def detect_channel_switch(
    db: AsyncSession,
    customer_id: str,
    new_channel: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if the customer is using a different channel than last time.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.
        new_channel: Current channel.

    Returns:
        Tuple of (switched: bool, previous_channel: str or None).
    """
    last_turn = await get_last_conversation_turn(db, customer_id)
    if last_turn:
        prev = last_turn.get("channel")
        if prev and prev != new_channel:
            return True, prev
    return False, None


# ============================================================
# MESSAGE QUERIES
# ============================================================

async def record_message(
    db: AsyncSession,
    conversation_id: str,
    ticket_id: Optional[str],
    role: str,
    content: str,
    channel: str,
    formatted_content: Optional[str] = None,
    agent_name: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Record a message in a conversation.

    Args:
        db: Async SQLAlchemy session.
        conversation_id: Parent conversation ID.
        ticket_id: Associated ticket ID.
        role: Message role (customer, agent, system).
        content: Raw message content.
        channel: Communication channel.
        formatted_content: Channel-formatted content.
        agent_name: Agent name (for agent messages).
        metadata: Extra metadata dict.

    Returns:
        Created message dict.
    """
    from production.database.models import Message

    message = Message(
        conversation_id=conversation_id,
        ticket_id=ticket_id,
        role=role,
        content=content,
        formatted_content=formatted_content,
        channel=channel,
        agent_name=agent_name,
        metadata=metadata or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message.to_dict()


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: str,
) -> list[dict]:
    """Get all messages in a conversation ordered by creation time."""
    from production.database.models import Message

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [m.to_dict() for m in messages]


# ============================================================
# ESCALATION QUERIES
# ============================================================

async def create_escalation(
    db: AsyncSession,
    ticket_id: str,
    customer_id: str,
    team: str,
    reason: str,
    sla: str,
    priority: str = "P2",
    summary: Optional[str] = None,
) -> dict:
    """
    Create an escalation record.

    Args:
        db: Async SQLAlchemy session.
        ticket_id: Ticket being escalated.
        customer_id: Customer ID.
        team: Target team name.
        reason: Reason for escalation.
        sla: SLA timeframe.
        priority: Escalation priority.
        summary: Optional summary.

    Returns:
        Created escalation dict.
    """
    from production.database.models import Escalation

    now = datetime.now(timezone.utc)
    escalation = Escalation(
        ticket_id=ticket_id,
        customer_id=customer_id,
        team=team,
        reason=reason,
        summary=summary,
        priority=priority,
        sla=sla,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(escalation)

    # Update ticket status
    await update_ticket_status(db, ticket_id, "escalated")

    # Increment customer escalated_tickets count
    from production.database.models import Customer
    stmt = select(Customer).where(Customer.customer_id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()
    if customer:
        customer.escalated_tickets += 1

    await db.commit()
    await db.refresh(escalation)

    logger.info("Created escalation %s for ticket %s → %s", escalation.escalation_id, ticket_id, team)
    return escalation.to_dict()


async def get_pending_escalations(
    db: AsyncSession,
    team: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get all pending escalations, optionally filtered by team.

    Args:
        db: Async SQLAlchemy session.
        team: Optional team filter.
        limit: Max results.

    Returns:
        List of escalation dicts sorted by priority and creation time.
    """
    from production.database.models import Escalation

    stmt = select(Escalation).where(Escalation.status == "pending")
    if team:
        stmt = stmt.where(Escalation.team == team)

    stmt = stmt.order_by(
        func.case(
            (Escalation.priority == "P1", 1),
            (Escalation.priority == "P2", 2),
            (Escalation.priority == "P3", 3),
            (Escalation.priority == "P4", 4),
        ),
        Escalation.created_at,
    ).limit(limit)

    result = await db.execute(stmt)
    escalations = result.scalars().all()
    return [e.to_dict() for e in escalations]


async def update_escalation_status(
    db: AsyncSession,
    escalation_id: str,
    status: str,
    assigned_to: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    """
    Update escalation status and optionally assign an agent.

    Args:
        db: Async SQLAlchemy session.
        escalation_id: Escalation ID.
        status: New status.
        assigned_to: Agent who took ownership.
        notes: Additional notes.

    Returns:
        True if updated.
    """
    from production.database.models import Escalation

    stmt = select(Escalation).where(Escalation.escalation_id == escalation_id)
    result = await db.execute(stmt)
    escalation = result.scalar_one_or_none()

    if not escalation:
        return False

    escalation.status = status
    escalation.updated_at = datetime.now(timezone.utc)
    if assigned_to:
        escalation.assigned_to = assigned_to
    if notes:
        escalation.notes = notes
    if status in ("resolved", "closed"):
        escalation.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    return True


# ============================================================
# METRICS & REPORTING
# ============================================================

async def get_ticket_metrics(
    db: AsyncSession,
    since: Optional[datetime] = None,
) -> dict:
    """
    Get aggregate ticket metrics.

    Args:
        db: Async SQLAlchemy session.
        since: Optional start datetime filter.

    Returns:
        Dict with counts by status, priority, channel, and topic.
    """
    from production.database.models import Ticket

    query = select(Ticket)
    if since:
        query = query.where(Ticket.created_at >= since)

    result = await db.execute(query)
    tickets = result.scalars().all()

    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_topic: dict[str, int] = {}

    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        by_channel[t.channel] = by_channel.get(t.channel, 0) + 1
        if t.topic:
            by_topic[t.topic] = by_topic.get(t.topic, 0) + 1

    return {
        "total": len(tickets),
        "by_status": by_status,
        "by_priority": by_priority,
        "by_channel": by_channel,
        "by_topic": by_topic,
    }


async def get_escalation_metrics(
    db: AsyncSession,
    since: Optional[datetime] = None,
) -> dict:
    """
    Get escalation metrics by team and status.

    Args:
        db: Async SQLAlchemy session.
        since: Optional start datetime filter.

    Returns:
        Dict with escalation counts.
    """
    from production.database.models import Escalation

    query = select(Escalation)
    if since:
        query = query.where(Escalation.created_at >= since)

    result = await db.execute(query)
    escalations = result.scalars().all()

    by_team: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}

    for e in escalations:
        by_team[e.team] = by_team.get(e.team, 0) + 1
        by_status[e.status] = by_status.get(e.status, 0) + 1
        by_priority[e.priority] = by_priority.get(e.priority, 0) + 1

    return {
        "total": len(escalations),
        "by_team": by_team,
        "by_status": by_status,
        "by_priority": by_priority,
        "pending_count": by_status.get("pending", 0),
    }


async def get_sentiment_trend(
    db: AsyncSession,
    customer_id: str,
) -> list[dict]:
    """
    Get sentiment trend for a customer from conversation history.

    Args:
        db: Async SQLAlchemy session.
        customer_id: Customer ID.

    Returns:
        List of {turn_number, sentiment_score, sentiment_label, created_at}.
    """
    from production.database.models import Conversation

    stmt = (
        select(Conversation.turn_number, Conversation.sentiment_score, Conversation.sentiment_label, Conversation.created_at)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.turn_number)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "turn_number": r.turn_number,
            "sentiment_score": r.sentiment_score,
            "sentiment_label": r.sentiment_label,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
