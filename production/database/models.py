"""
TaskFlow AI Support Agent — SQLAlchemy ORM Models
CRM Digital FTE Factory Final Hackathon 5

Mirrors production/database/schema.sql for use with async SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, INET
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


# ============================================================
# 1. CUSTOMERS
# ============================================================

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(20), primary_key=True, server_default=text("'CUST-' || LPAD(NEXTVAL('customer_seq')::TEXT, 4, '0')"))
    name = Column(String(200), nullable=False)
    email = Column(String(320), unique=True)
    phone = Column(String(30), unique=True)
    tier = Column(String(20), nullable=False, server_default=text("'unknown'"))
    channels_seen = Column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    total_tickets = Column(Integer, nullable=False, server_default=text("0"))
    resolved_tickets = Column(Integer, nullable=False, server_default=text("0"))
    escalated_tickets = Column(Integer, nullable=False, server_default=text("0"))
    sentiment_history = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    topic_history = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    last_contact = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    tickets = relationship("Ticket", back_populates="customer", lazy="select")
    conversations = relationship("Conversation", back_populates="customer", lazy="select")
    escalations = relationship("Escalation", back_populates="customer", lazy="select")

    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="chk_email_or_phone"),
        Index("idx_customers_email", "email", postgresql_where=text("email IS NOT NULL")),
        Index("idx_customers_phone", "phone", postgresql_where=text("phone IS NOT NULL")),
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

    ticket_id = Column(String(20), primary_key=True, server_default=text("'TICKET-' || LPAD(NEXTVAL('ticket_seq')::TEXT, 4, '0')"))
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(10), nullable=False)
    subject = Column(String(500))
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'open'"))
    priority = Column(String(4), nullable=False, server_default=text("'P3'"))
    topic = Column(String(50))
    sentiment_score = Column(Integer, server_default=text("0"))
    sentiment_label = Column(String(20))
    ai_attempts = Column(Integer, nullable=False, server_default=text("0"))
    is_follow_up = Column(Boolean, nullable=False, server_default=text("FALSE"))
    channel_switch = Column(Boolean, nullable=False, server_default=text("FALSE"))
    previous_channel = Column(String(10))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
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
        Index("idx_tickets_priority_status", "priority", "status", postgresql_where=text("status IN ('open', 'escalated')")),
    )

    to_dict = _to_dict


# ============================================================
# 3. CONVERSATIONS
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="SET NULL"))
    turn_number = Column(Integer, nullable=False)
    channel = Column(String(10), nullable=False)
    topic = Column(String(50))
    sentiment_score = Column(Integer, server_default=text("0"))
    sentiment_label = Column(String(20))
    resolution_status = Column(String(20), nullable=False, server_default=text("'new'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

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
        Index("idx_conversations_customer_turn", "customer_id", "turn_number"),
    )

    to_dict = _to_dict


# ============================================================
# 4. MESSAGES
# ============================================================

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="SET NULL"))
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    formatted_content = Column(Text)
    channel = Column(String(10), nullable=False)
    agent_name = Column(String(200))
    message_metadata = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

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
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    to_dict = _to_dict


# ============================================================
# 5. ESCALATIONS
# ============================================================

class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column(String(20), primary_key=True, server_default=text("'ESC-' || LPAD(NEXTVAL('escalation_seq')::TEXT, 4, '0')"))
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    team = Column(String(20), nullable=False)
    team_email = Column(String(320))
    reason = Column(Text, nullable=False)
    summary = Column(Text)
    priority = Column(String(4), nullable=False, server_default=text("'P2'"))
    sla = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    assigned_to = Column(String(200))
    notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

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
        Index("idx_escalations_team_status", "team", "status", postgresql_where=text("status = 'pending'")),
    )

    to_dict = _to_dict


# ============================================================
# 6. KNOWLEDGE BASE
# ============================================================

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    kb_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    topic = Column(String(50), nullable=False, unique=True)
    title = Column(String(200), nullable=False)
    overview = Column(Text, nullable=False)
    content = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    keywords = Column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    version = Column(Integer, nullable=False, server_default=text("1"))
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_by = Column(String(200), nullable=False, server_default=text("'system'"))
    updated_by = Column(String(200), nullable=False, server_default=text("'system'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint("array_length(keywords, 1) > 0", name="chk_keywords_not_empty"),
        Index("idx_kb_topic", "topic"),
        Index("idx_kb_active", "is_active", postgresql_where=text("is_active = TRUE")),
    )

    to_dict = _to_dict


# ============================================================
# 7. IDENTITY MAP
# ============================================================

class IdentityMap(Base):
    __tablename__ = "identity_map"

    identity_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    customer_id = Column(String(20), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    identifier_type = Column(String(10), nullable=False)
    identifier_value = Column(String(320), nullable=False, unique=True)
    is_primary = Column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint("identifier_type IN ('email', 'phone')", name="chk_identifier_type"),
        Index("idx_identity_customer", "customer_id"),
        Index("idx_identity_value", "identifier_value"),
        Index("idx_identity_type_value", "identifier_type", "identifier_value"),
    )

    to_dict = _to_dict


# ============================================================
# 8. AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    performed_by = Column(String(200), nullable=False, server_default=text("'system'"))
    ip_address = Column(INET)
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_performed_by", "performed_by"),
    )

    to_dict = _to_dict


# ============================================================
# 9. SYSTEM CONFIG
# ============================================================

class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key = Column(String(100), primary_key=True)
    config_value = Column(JSONB, nullable=False)
    description = Column(Text)
    updated_by = Column(String(200))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    to_dict = _to_dict
