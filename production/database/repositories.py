"""
TaskFlow AI Support Agent — Repository Layer
CRM Digital FTE Factory Final Hackathon 5

Repository pattern for clean, testable database access.
Each repository encapsulates CRUD for one aggregate root.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from production.database.models import (
    Base,
    Customer,
    Ticket,
    Conversation,
    Message,
    Escalation,
    KnowledgeBase,
)

logger = logging.getLogger(__name__)


# ============================================================
# CUSTOMER REPOSITORY
# ============================================================

class CustomerRepository:
    """CRUD + identity resolution for customers."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_email(self, email: str) -> Optional[Customer]:
        stmt = select(Customer).where(func.lower(Customer.email) == email.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_phone(self, phone: str) -> Optional[Customer]:
        stmt = select(Customer).where(Customer.phone == phone)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_id(self, customer_id: str) -> Optional[Customer]:
        stmt = select(Customer).where(Customer.customer_id == customer_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_or_create(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        defaults: Optional[dict] = None,
    ) -> Customer:
        """Find existing customer by email/phone or create a new one."""
        if email:
            existing = await self.find_by_email(email)
            if existing:
                return existing
        if phone:
            existing = await self.find_by_phone(phone)
            if existing:
                return existing

        now = _utcnow()
        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            tier="unknown",
            channels_seen=[],
            total_tickets=0,
            resolved_tickets=0,
            escalated_tickets=0,
            sentiment_history=[],
            topic_history=[],
            last_contact=now,
            created_at=now,
            updated_at=now,
        )
        if defaults:
            for k, v in defaults.items():
                setattr(customer, k, v)

        self._session.add(customer)
        await self._session.commit()
        await self._session.refresh(customer)
        logger.info("Created new customer: %s (%s)", name, customer.customer_id)
        return customer

    async def add_channel(self, customer_id: str, channel: str) -> bool:
        customer = await self.find_by_id(customer_id)
        if not customer:
            return False
        if channel not in customer.channels_seen:
            customer.channels_seen = customer.channels_seen + [channel]
            customer.updated_at = _utcnow()
            await self._session.commit()
            return True
        return False

    async def append_sentiment(self, customer_id: str, score: int) -> bool:
        customer = await self.find_by_id(customer_id)
        if not customer:
            return False
        history = customer.sentiment_history or []
        history.append([_utcnow().isoformat(), score])
        customer.sentiment_history = history
        customer.updated_at = _utcnow()
        await self._session.commit()
        return True

    async def increment_ticket_count(self, customer_id: str) -> None:
        customer = await self.find_by_id(customer_id)
        if customer:
            customer.total_tickets += 1
            customer.last_contact = _utcnow()
            await self._session.commit()

    async def increment_escalated_tickets(self, customer_id: str) -> None:
        customer = await self.find_by_id(customer_id)
        if customer:
            customer.escalated_tickets += 1
            await self._session.commit()


# ============================================================
# TICKET REPOSITORY
# ============================================================

class TicketRepository:
    """CRUD for tickets."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
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
    ) -> Ticket:
        now = _utcnow()
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
        self._session.add(ticket)
        await self._session.commit()
        await self._session.refresh(ticket)
        logger.info("Created ticket %s for customer %s", ticket.ticket_id, customer_id)
        return ticket

    async def find_by_id(self, ticket_id: str) -> Optional[Ticket]:
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.customer), selectinload(Ticket.messages))
            .where(Ticket.ticket_id == ticket_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, ticket_id: str, status: str, ai_attempts: Optional[int] = None) -> bool:
        ticket = await self.find_by_id(ticket_id)
        if not ticket:
            return False
        ticket.status = status
        ticket.updated_at = _utcnow()
        if ai_attempts is not None:
            ticket.ai_attempts = ai_attempts
        if status in ("resolved", "closed"):
            ticket.resolved_at = _utcnow()
        if status == "closed":
            ticket.closed_at = _utcnow()
        await self._session.commit()
        return True

    async def increment_ai_attempts(self, ticket_id: str) -> int:
        ticket = await self.find_by_id(ticket_id)
        if not ticket:
            return 0
        ticket.ai_attempts += 1
        ticket.updated_at = _utcnow()
        await self._session.commit()
        return ticket.ai_attempts


# ============================================================
# CONVERSATION REPOSITORY
# ============================================================

class ConversationRepository:
    """Manage conversation turns and messages."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_turn(
        self,
        customer_id: str,
        channel: str,
        ticket_id: Optional[str] = None,
        topic: Optional[str] = None,
        sentiment_score: int = 0,
        sentiment_label: str = "neutral",
        resolution_status: str = "new",
    ) -> Conversation:
        # Auto-increment turn number
        stmt = select(func.coalesce(func.max(Conversation.turn_number), 0)).where(
            Conversation.customer_id == customer_id
        )
        result = await self._session.execute(stmt)
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
            created_at=_utcnow(),
        )
        self._session.add(turn)
        await self._session.commit()
        await self._session.refresh(turn)
        return turn

    async def get_last_turn(self, customer_id: str) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.customer_id == customer_id)
            .order_by(desc(Conversation.turn_number))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


# ============================================================
# MESSAGE REPOSITORY
# ============================================================

class MessageRepository:
    """Record and retrieve messages."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        conversation_id: str,
        ticket_id: Optional[str],
        role: str,
        content: str,
        channel: str,
        formatted_content: Optional[str] = None,
        agent_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            role=role,
            content=content,
            formatted_content=formatted_content,
            channel=channel,
            agent_name=agent_name,
            message_metadata=metadata or {},
            created_at=_utcnow(),
        )
        self._session.add(msg)
        await self._session.commit()
        await self._session.refresh(msg)
        return msg


# ============================================================
# ESCALATION REPOSITORY
# ============================================================

class EscalationRepository:
    """Create and manage escalations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        ticket_id: str,
        customer_id: str,
        team: str,
        reason: str,
        sla: str,
        priority: str = "P2",
        summary: Optional[str] = None,
    ) -> Escalation:
        now = _utcnow()
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
        self._session.add(escalation)
        await self._session.commit()
        await self._session.refresh(escalation)
        logger.info("Created escalation %s for ticket %s → %s", escalation.escalation_id, ticket_id, team)
        return escalation


# ============================================================
# KNOWLEDGE BASE REPOSITORY
# ============================================================

class KnowledgeBaseRepository:
    """Search and retrieve KB articles."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_topic(self, topic: str) -> Optional[KnowledgeBase]:
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.topic == topic,
            KnowledgeBase.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(self, query: str, limit: int = 5) -> list[KnowledgeBase]:
        """Simple keyword search against KB articles."""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.is_active == True,  # noqa: E712
                or_(
                    KnowledgeBase.title.ilike(f"%{query}%"),
                    KnowledgeBase.overview.ilike(f"%{query}%"),
                ),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# ============================================================
# HELPERS
# ============================================================

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
