"""
TaskFlow AI Support Agent — SQLAlchemy ORM Models
CRM Digital FTE Factory Final Hackathon 5

Modified for SQLite compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Helpers ──

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(self) -> dict:
    """Convert model instance to a plain dict (excludes SA internals)."""
    result: dict[str, Any] = {}
    for col in self.__table__.columns:  # type: ignore[attr-defined]
        val = getattr(self, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        result[col.name] = val
    return result


def generate_uuid():
    return str(uuid.uuid4())


# ============================================================
# 1. CUSTOMERS
# ============================================================

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(320), unique=True)
    phone = Column(String(30), unique=True)
    tier = Column(String(20), nullable=False, default="unknown")
    channels_seen = Column(JSON, nullable=False, default=list) # SQLite: use JSON for arrays
    total_tickets = Column(Integer, nullable=False, default=0)
    resolved_tickets = Column(Integer, nullable=False, default=0)
    escalated_tickets = Column(Integer, nullable=False, default=0)
    sentiment_history = Column(JSON, nullable=False, default=list)
    topic_history = Column(JSON, nullable=False, default=list)
    last_contact = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    tickets = relationship("Ticket", back_populates="customer", lazy="select")
    conversations = relationship("Conversation", back_populates="customer", lazy="select")
    escalations = relationship("Escalation", back_populates="customer", lazy="select")

    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="chk_email_or_phone"),
        Index("idx_customers_email", "email"),
        Index("idx_customers_phone", "phone"),
        Index("idx_customers_tier", "tier"),
        Index("idx_customers_last_contact", "last_contact"),
        Index("idx_customers_created_at", "created_at"),
    )

    to_dict = _to_dict


# ============================================================
# 2. TICKETS
# ============================================================

class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String(20), primary_key=True)
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(10), nullable=False)
    subject = Column(String(500))
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    priority = Column(String(4), nullable=False, default="P3")
    topic = Column(String(50))
    sentiment_score = Column(Integer, default=0)
    sentiment_label = Column(String(20))
    ai_attempts = Column(Integer, nullable=False, default=0)
    is_follow_up = Column(Boolean, nullable=False, default=False)
    channel_switch = Column(Boolean, nullable=False, default=False)
    previous_channel = Column(String(10))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))

    # Relationships
    customer = relationship("Customer", back_populates="tickets")
    messages = relationship("Message", back_populates="ticket", lazy="select")
    conversations = relationship("Conversation", back_populates="ticket", lazy="select")
    escalations = relationship("Escalation", back_populates="ticket", lazy="select")

    __table_args__ = (
        CheckConstraint("sentiment_score BETWEEN -2 AND 2", name="chk_sentiment_score"),
        Index("idx_tickets_customer", "customer_id"),
        Index("idx_tickets_status", "status"),
        Index("idx_tickets_priority", "priority"),
        Index("idx_tickets_channel", "channel"),
        Index("idx_tickets_topic", "topic"),
        Index("idx_tickets_created_at", "created_at"),
        Index("idx_tickets_updated_at", "updated_at"),
        Index("idx_tickets_customer_status", "customer_id", "status"),
    )

    to_dict = _to_dict


# ============================================================
# 3. CONVERSATIONS
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String(36), primary_key=True, default=generate_uuid)
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="SET NULL"))
    turn_number = Column(Integer, nullable=False)
    channel = Column(String(10), nullable=False)
    topic = Column(String(50))
    sentiment_score = Column(Integer, default=0)
    sentiment_label = Column(String(20))
    resolution_status = Column(String(20), nullable=False, default="new")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="conversations")
    ticket = relationship("Ticket", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", lazy="select")

    __table_args__ = (
        CheckConstraint("sentiment_score BETWEEN -2 AND 2", name="chk_conv_sentiment"),
        CheckConstraint("turn_number > 0", name="chk_turn_number"),
        UniqueConstraint("customer_id", "turn_number", name="uq_customer_turn"),
        Index("idx_conversations_customer", "customer_id"),
        Index("idx_conversations_ticket", "ticket_id"),
        Index("idx_conversations_created_at", "created_at"),
        Index("idx_conversations_status", "resolution_status"),
    )

    to_dict = _to_dict


# ============================================================
# 4. MESSAGES
# ============================================================

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="SET NULL"))
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    formatted_content = Column(Text)
    channel = Column(String(10), nullable=False)
    agent_name = Column(String(200))
    message_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    ticket = relationship("Ticket", back_populates="messages")

    __table_args__ = (
        CheckConstraint("LENGTH(content) > 0 AND LENGTH(content) <= 50000", name="chk_content_length"),
        Index("idx_messages_conversation", "conversation_id"),
        Index("idx_messages_ticket", "ticket_id"),
        Index("idx_messages_role", "role"),
        Index("idx_messages_channel", "channel"),
        Index("idx_messages_created_at", "created_at"),
    )

    to_dict = _to_dict


# ============================================================
# 5. ESCALATIONS
# ============================================================

class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column(String(20), primary_key=True)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    team = Column(String(20), nullable=False)
    team_email = Column(String(320))
    reason = Column(Text, nullable=False)
    summary = Column(Text)
    priority = Column(String(4), nullable=False, default="P2")
    sla = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    assigned_to = Column(String(200))
    notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    ticket = relationship("Ticket", back_populates="escalations")
    customer = relationship("Customer", back_populates="escalations")

    __table_args__ = (
        CheckConstraint("LENGTH(reason) <= 2000", name="chk_reason_length"),
        CheckConstraint("summary IS NULL OR LENGTH(summary) <= 10000", name="chk_summary_length"),
        Index("idx_escalations_ticket", "ticket_id"),
        Index("idx_escalations_customer", "customer_id"),
        Index("idx_escalations_team", "team"),
        Index("idx_escalations_status", "status"),
        Index("idx_escalations_priority", "priority"),
        Index("idx_escalations_created_at", "created_at"),
    )

    to_dict = _to_dict


# ============================================================
# 6. KNOWLEDGE BASE
# ============================================================

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    kb_id = Column(String(36), primary_key=True, default=generate_uuid)
    topic = Column(String(50), nullable=False, unique=True)
    title = Column(String(200), nullable=False)
    overview = Column(Text, nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    keywords = Column(JSON, nullable=False, default=list) # SQLite use JSON
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(200), nullable=False, default="system")
    updated_by = Column(String(200), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_kb_topic", "topic"),
        Index("idx_kb_active", "is_active"),
    )

    to_dict = _to_dict


# ============================================================
# 7. IDENTITY MAP
# ============================================================

class IdentityMap(Base):
    __tablename__ = "identity_map"

    identity_id = Column(String(36), primary_key=True, default=generate_uuid)
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    identifier_type = Column(String(10), nullable=False)
    identifier_value = Column(String(320), nullable=False, unique=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint("identifier_type IN ('email', 'phone')", name="chk_identifier_type"),
        Index("idx_identity_customer", "customer_id"),
        Index("idx_identity_value", "identifier_value"),
    )

    to_dict = _to_dict


# ============================================================
# 8. AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    old_values = Column(JSON)
    new_values = Column(JSON)
    performed_by = Column(String(200), nullable=False, default="system")
    ip_address = Column(String(45)) # SQLite use String for IP
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created_at", "created_at"),
    )

    to_dict = _to_dict


# ============================================================
# 9. SYSTEM CONFIG
# ============================================================

class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key = Column(String(100), primary_key=True)
    config_value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_by = Column(String(200))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    to_dict = _to_dict
