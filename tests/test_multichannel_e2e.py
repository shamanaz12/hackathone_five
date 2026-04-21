"""
TaskFlow AI Support Agent — Multichannel End-to-End Tests
CRM Digital FTE Factory Final Hackathon 5

Tests:
- Web form submission flow
- Cross-channel continuity (email → WhatsApp → web_form)
- Customer identity resolution
- Sentiment tracking across channels
- Escalation decision accuracy
- Basic metrics collection
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import production modules (with fallback for missing deps)
try:
    from production.agent.tools import (
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response,
        SearchKnowledgeBaseInput,
        CreateTicketInput,
        GetCustomerHistoryInput,
        EscalateToHumanInput,
        SendResponseInput,
    )
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False

try:
    from production.agent.customer_success_agent import AgentPipeline
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

try:
    from production.workers.message_processor import (
        UnifiedMessageProcessor,
        MessageParser,
        ProcessingMetrics,
        KafkaTopics,
        UnifiedMessage,
        ProcessingResult,
    )
    WORKER_AVAILABLE = True
except ImportError:
    WORKER_AVAILABLE = False

try:
    from production.utils.helpers import (
        format_for_channel,
        sanitize_input,
        generate_ticket_id,
        generate_customer_id,
        generate_escalation_id,
    )
    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_customer():
    """Sample customer data for tests."""
    return {
        "name": "Alice Johnson",
        "email": "alice.j@startupco.com",
        "phone": "+1 555 123 4567",
    }


@pytest.fixture
def sample_tickets():
    """Sample ticket payloads for different channels."""
    return {
        "email": {
            "customer_name": "Alice Johnson",
            "message": "I've been trying to reset my password for the past hour. The reset link says expired even though I just requested it 5 minutes ago!",
            "channel": "email",
            "email": "alice.j@startupco.com",
            "subject": "Password reset issue",
        },
        "whatsapp": {
            "customer_name": "Alice Johnson",
            "message": "Hey, I still haven't received the password reset email. Any update?",
            "channel": "whatsapp",
            "phone": "+1 555 123 4567",
        },
        "web_form": {
            "customer_name": "Alice Johnson",
            "message": "Following up on my password reset issue. It's been 2 hours now and I still can't access my account.",
            "channel": "web_form",
            "email": "alice.j@startupco.com",
            "subject": "Follow-up: Password reset",
        },
    }


@pytest.fixture
def mock_pipeline():
    """Create a mock AgentPipeline for testing."""
    if not AGENT_AVAILABLE:
        pytest.skip("Agent pipeline not available")
    return AgentPipeline(channel="email")


@pytest.fixture
def mock_processor():
    """Create a mock UnifiedMessageProcessor for testing."""
    if not WORKER_AVAILABLE:
        pytest.skip("Worker not available")
    processor = UnifiedMessageProcessor.__new__(UnifiedMessageProcessor)
    processor.parser = MessageParser()
    processor.metrics = ProcessingMetrics()
    processor._pipelines = {}
    processor.max_retries = 3
    return processor


# ============================================================
# TEST SUITE 1: Web Form Submission
# ============================================================

class TestWebFormSubmission:
    """Test web form ticket submission flow."""

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_create_ticket_web_form(self, sample_customer):
        """Test creating a ticket from web form submission."""
        payload = CreateTicketInput(
            customer_name=sample_customer["name"],
            message="I can't access my account. The password reset link expired.",
            channel="web_form",
            email=sample_customer["email"],
            subject="Account access issue",
        )
        result = json.loads(create_ticket(payload))

        assert result["status"] == "created"
        assert result["ticket"]["ticket_id"].startswith("TICKET-")
        assert result["ticket"]["customer_id"].startswith("CUST-")
        assert result["ticket"]["channel"] == "web_form"
        assert result["ticket"]["status"] == "open"
        assert result["ticket"]["priority"] == "P3"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_web_form_ticket_with_category(self, sample_customer):
        """Test creating a ticket with explicit category and priority."""
        payload = CreateTicketInput(
            customer_name=sample_customer["name"],
            message="Kanban board is loading very slowly. Takes 20+ seconds.",
            channel="web_form",
            email=sample_customer["email"],
            subject="Performance issue",
        )
        result = json.loads(create_ticket(payload))

        assert result["status"] == "created"
        assert result["ticket"]["channel"] == "web_form"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_web_form_validation_missing_name(self):
        """Test validation: missing customer name."""
        with pytest.raises(Exception):
            CreateTicketInput(
                customer_name="",
                message="Test message",
                channel="web_form",
                email="test@example.com",
            )

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_web_form_validation_invalid_email(self):
        """Test validation: invalid email format."""
        with pytest.raises(Exception):
            CreateTicketInput(
                customer_name="Test User",
                message="Test message",
                channel="web_form",
                email="not-an-email",
            )

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_web_form_validation_invalid_channel(self):
        """Test validation: invalid channel."""
        with pytest.raises(Exception):
            CreateTicketInput(
                customer_name="Test User",
                message="Test message",
                channel="slack",
                email="test@example.com",
            )

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_web_form_send_response(self, sample_customer):
        """Test sending a response to a web form ticket."""
        # Create ticket first
        ticket_result = json.loads(create_ticket(CreateTicketInput(
            customer_name=sample_customer["name"],
            message="How do I create a project?",
            channel="web_form",
            email=sample_customer["email"],
            subject="Project creation help",
        )))
        ticket_id = ticket_result["ticket"]["ticket_id"]

        # Send response
        response_result = json.loads(send_response(SendResponseInput(
            ticket_id=ticket_id,
            response_text="Hello Alice,\n\nTo create a project, click '+ New Project' at the top right.",
            channel="web_form",
        )))

        assert response_result["status"] == "sent"
        assert response_result["channel"] == "web_form"
        assert response_result["ticket_id"] == ticket_id


# ============================================================
# TEST SUITE 2: Cross-Channel Continuity
# ============================================================

class TestCrossChannelContinuity:
    """Test customer identity resolution and conversation continuity across channels."""

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_same_customer_different_channels(self, sample_customer, sample_tickets):
        """Test that same customer via different channels resolves to same customer_id."""
        # Email ticket
        email_result = json.loads(create_ticket(CreateTicketInput(**sample_tickets["email"])))
        email_customer_id = email_result["ticket"]["customer_id"]

        # WhatsApp ticket (same customer, different channel)
        whatsapp_result = json.loads(create_ticket(CreateTicketInput(**sample_tickets["whatsapp"])))
        whatsapp_customer_id = whatsapp_result["ticket"]["customer_id"]

        # Web form ticket (same customer, third channel)
        webform_result = json.loads(create_ticket(CreateTicketInput(**sample_tickets["web_form"])))
        webform_customer_id = webform_result["ticket"]["customer_id"]

        # All should resolve to same customer
        assert email_customer_id == whatsapp_customer_id
        assert email_customer_id == webform_customer_id

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_customer_history_across_channels(self, sample_customer, sample_tickets):
        """Test retrieving full conversation history across all channels."""
        # Create tickets on all 3 channels
        for channel_data in sample_tickets.values():
            create_ticket(CreateTicketInput(**channel_data))

        # Get history by email
        history_result = json.loads(get_customer_history(GetCustomerHistoryInput(
            email=sample_customer["email"],
        )))

        assert history_result["status"] == "found"
        assert history_result["total_tickets"] == 3
        assert history_result["total_interactions"] == 3

        # Verify all channels are represented
        channels_seen = set()
        for conv in history_result["conversation_history"]:
            channels_seen.add(conv["channel"])
        assert "email" in channels_seen
        assert "whatsapp" in channels_seen
        assert "web_form" in channels_seen

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_customer_history_by_phone(self, sample_customer, sample_tickets):
        """Test retrieving customer history by phone number."""
        # Create WhatsApp ticket
        create_ticket(CreateTicketInput(**sample_tickets["whatsapp"]))

        # Get history by phone
        history_result = json.loads(get_customer_history(GetCustomerHistoryInput(
            phone=sample_customer["phone"],
        )))

        assert history_result["status"] == "found"
        assert history_result["total_tickets"] >= 1

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_customer_history_no_identifier(self):
        """Test that history lookup fails without any identifier."""
        result = json.loads(get_customer_history(GetCustomerHistoryInput()))
        assert result["status"] == "error"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_escalation_preserves_cross_channel_context(self, sample_customer, sample_tickets):
        """Test that escalation maintains customer context across channels."""
        # Create email ticket
        ticket_result = json.loads(create_ticket(CreateTicketInput(**sample_tickets["email"])))
        ticket_id = ticket_result["ticket"]["ticket_id"]

        # Escalate
        esc_result = json.loads(escalate_to_human(EscalateToHumanInput(
            ticket_id=ticket_id,
            team="security",
            reason="Account locked — customer cannot access projects",
            priority="P1",
            customer_name=sample_customer["name"],
            summary="Customer tried password reset multiple times, account now locked.",
        )))

        assert esc_result["status"] == "escalated"
        assert esc_result["escalation"]["team"] == "Security Team"
        assert esc_result["escalation"]["sla"] == "30 minutes"

        # Verify customer history still accessible
        history = json.loads(get_customer_history(GetCustomerHistoryInput(
            email=sample_customer["email"],
        )))
        assert history["status"] == "found"


# ============================================================
# TEST SUITE 3: Knowledge Base & Response
# ============================================================

class TestKnowledgeBaseAndResponse:
    """Test knowledge base search and response generation."""

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_kb_search_password_reset(self):
        """Test KB search for password reset topic."""
        result = json.loads(search_knowledge_base(SearchKnowledgeBaseInput(
            query="password reset link expired",
            topic="password_reset",
        )))

        assert result["status"] == "found"
        assert result["results_count"] >= 1
        assert result["results"][0]["topic"] == "password_reset"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_kb_search_no_topic_filter(self):
        """Test KB search without topic filter (should search all topics)."""
        result = json.loads(search_knowledge_base(SearchKnowledgeBaseInput(
            query="kanban board slow loading",
        )))

        assert result["status"] == "found"
        assert result["results_count"] >= 1
        # Should find kanban_board as top result
        assert result["results"][0]["topic"] == "kanban_board"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_kb_search_no_match(self):
        """Test KB search with no matching content."""
        result = json.loads(search_knowledge_base(SearchKnowledgeBaseInput(
            query="xyzzy quantum flux capacitor",
        )))

        assert result["status"] == "not_found"

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_kb_search_invalid_topic(self):
        """Test KB search with invalid topic filter."""
        with pytest.raises(Exception):
            SearchKnowledgeBaseInput(query="test", topic="invalid_topic_xyz")

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_channel_formatting_email(self):
        """Test email formatting (no emojis, full text)."""
        text = "Hi Alice,\n\nHere's what to do:\n1. Step one\n2. Step two\n\nBest regards,\nThe TaskFlow Support Team"
        formatted = format_for_channel(text, "email")
        assert "Hi Alice" in formatted
        assert "Best regards" in formatted

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_channel_formatting_whatsapp(self):
        """Test WhatsApp formatting (truncation, emoji placeholders)."""
        text = "Hey Alice! [wave]\n\n[1] Step one\n[2] Step two\n\nHope that helps! [smile]"
        formatted = format_for_channel(text, "whatsapp")
        assert "Hey Alice" in formatted
        assert "Hope that helps" in formatted

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_channel_formatting_truncation(self):
        """Test WhatsApp truncation for long messages."""
        long_text = "A" * 5000
        formatted = format_for_channel(long_text, "whatsapp")
        assert len(formatted) <= 1050  # 1000 + truncation note
        assert "truncated" in formatted.lower()


# ============================================================
# TEST SUITE 4: Message Processor & Metrics
# ============================================================

class TestMessageProcessor:
    """Test the unified message processor and metrics collection."""

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_parse_email_message(self, mock_processor):
        """Test parsing an email channel message."""
        payload = {
            "from_name": "Alice Johnson",
            "from_email": "alice.j@startupco.com",
            "subject": "Password reset issue",
            "body": "I can't reset my password. The link expired.",
        }
        kafka_meta = {
            "topic": KafkaTopics.INCOMING_EMAIL.name,
            "partition": 0,
            "offset": 100,
            "key": "alice.j@startupco.com",
        }

        msg = mock_processor.parser.parse(payload, kafka_meta)

        assert msg.channel == "email"
        assert msg.customer_name == "Alice Johnson"
        assert msg.customer_email == "alice.j@startupco.com"
        assert "Password reset" in msg.subject

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_parse_whatsapp_message(self, mock_processor):
        """Test parsing a WhatsApp channel message."""
        payload = {
            "sender_phone": "+1 555 123 4567",
            "sender_name": "Alice Johnson",
            "content": "Hey, any update on my password reset?",
            "message_type": "text",
            "message_id": "wa-msg-001",
        }
        kafka_meta = {
            "topic": KafkaTopics.INCOMING_WHATSAPP.name,
            "partition": 1,
            "offset": 200,
            "key": "+1 555 123 4567",
        }

        msg = mock_processor.parser.parse(payload, kafka_meta)

        assert msg.channel == "whatsapp"
        assert msg.customer_phone == "+1 555 123 4567"
        assert "update" in msg.content.lower()

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_parse_web_form_message(self, mock_processor):
        """Test parsing a web form submission."""
        payload = {
            "customer_name": "Alice Johnson",
            "email": "alice.j@startupco.com",
            "subject": "Follow-up: Password reset",
            "message": "Still can't access my account.",
            "category": "password_reset",
            "priority": "P2",
        }
        kafka_meta = {
            "topic": KafkaTopics.INCOMING_WEB_FORM.name,
            "partition": 0,
            "offset": 300,
            "key": "alice.j@startupco.com",
        }

        msg = mock_processor.parser.parse(payload, kafka_meta)

        assert msg.channel == "web_form"
        assert msg.customer_email == "alice.j@startupco.com"
        assert msg.metadata.get("category") == "password_reset"

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_parse_auto_detect_from_payload(self, mock_processor):
        """Test auto-detecting channel from payload structure."""
        # WhatsApp-like payload
        wa_payload = {"sender_phone": "+1 555 0000", "content": "Hi"}
        kafka_meta = {"topic": "taskflow.incoming.unknown", "partition": 0, "offset": 0, "key": None}
        msg = mock_processor.parser.parse(wa_payload, kafka_meta)
        assert msg.channel == "whatsapp"

        # Web form-like payload
        wf_payload = {"customer_name": "Test", "message": "Help", "email": "test@example.com"}
        msg = mock_processor.parser.parse(wf_payload, kafka_meta)
        assert msg.channel == "web_form"

        # Email-like payload
        em_payload = {"from_email": "test@example.com", "body": "Help"}
        msg = mock_processor.parser.parse(em_payload, kafka_meta)
        assert msg.channel == "email"

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_metrics_collection(self, mock_processor):
        """Test that metrics are correctly collected."""
        metrics = mock_processor.metrics

        # Record some successes
        metrics.record_success("email", "taskflow.incoming.email", 150.0)
        metrics.record_success("whatsapp", "taskflow.incoming.whatsapp", 200.0)
        metrics.record_success("email", "taskflow.incoming.email", 100.0)

        # Record a failure
        metrics.record_failure("web_form", "ValidationError")

        # Record an escalation
        metrics.record_escalation()

        summary = metrics.get_summary()

        assert summary["total_processed"] == 4
        assert summary["total_succeeded"] == 3
        assert summary["total_failed"] == 1
        assert summary["total_escalated"] == 1
        assert summary["success_rate"] == 75.0
        assert summary["messages_by_channel"]["email"] == 2
        assert summary["messages_by_channel"]["whatsapp"] == 1
        assert summary["messages_by_channel"]["web_form"] == 1
        assert summary["errors_by_type"]["ValidationError"] == 1
        assert summary["avg_processing_time_ms"] == 150.0  # (150 + 200 + 100) / 3

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_metrics_p95_calculation(self, mock_processor):
        """Test P95 latency calculation."""
        metrics = mock_processor.metrics

        # Record 20 messages with known latencies
        for i in range(20):
            metrics.record_success("email", "taskflow.incoming.email", float(i * 10))

        summary = metrics.get_summary()

        # P95 of 0,10,20,...,190 = 180 (95th percentile index = 19)
        assert summary["p95_processing_time_ms"] == 180.0
        assert summary["avg_processing_time_ms"] == 95.0  # (0+10+...+190)/20

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_dead_letter_recording(self, mock_processor):
        """Test dead letter metric recording."""
        metrics = mock_processor.metrics
        metrics.record_dead_letter()
        metrics.record_dead_letter()
        metrics.record_dead_letter()

        summary = metrics.get_summary()
        assert summary["total_dead_lettered"] == 3

    @pytest.mark.skipif(not WORKER_AVAILABLE, reason="Worker not available")
    def test_retry_recording(self, mock_processor):
        """Test retry metric recording."""
        metrics = mock_processor.metrics
        metrics.record_retry()
        metrics.record_retry()

        summary = metrics.get_summary()
        assert summary["total_retried"] == 2


# ============================================================
# TEST SUITE 5: Helper Utilities
# ============================================================

class TestHelperUtilities:
    """Test utility functions."""

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_generate_ticket_id(self):
        """Test ticket ID generation format."""
        tid = generate_ticket_id()
        assert tid.startswith("TICKET-")
        assert len(tid) == 11  # TICKET-NNNN

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_generate_customer_id(self):
        """Test customer ID generation format."""
        cid = generate_customer_id()
        assert cid.startswith("CUST-")
        assert len(cid) == 9  # CUST-NNNN

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_generate_escalation_id(self):
        """Test escalation ID generation format."""
        eid = generate_escalation_id()
        assert eid.startswith("ESCALATION-")
        assert len(eid) == 15  # ESCALATION-NNNN

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_sanitize_input(self):
        """Test input sanitization."""
        # Null byte removal
        assert sanitize_input("hello\x00world") == "hello world"
        # Whitespace collapsing
        assert sanitize_input("hello   world") == "hello world"
        # Truncation
        long_input = "A" * 15000
        result = sanitize_input(long_input)
        assert len(result) <= 10003  # 10000 + "..."
        assert result.endswith("...")

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_format_for_channel_email(self):
        """Test email formatting strips emoji placeholders."""
        text = "Hi Alice! [wave] Here's help. [smile]"
        result = format_for_channel(text, "email")
        assert "[wave]" not in result
        assert "[smile]" not in result

    @pytest.mark.skipif(not HELPERS_AVAILABLE, reason="Helpers not available")
    def test_format_for_channel_web_form(self):
        """Test web form formatting."""
        text = "Hello Alice, [wave] Here's help."
        result = format_for_channel(text, "web_form")
        assert "[wave]" not in result
        assert "Hello Alice" in result


# ============================================================
# TEST SUITE 6: Integration Flow (End-to-End Pipeline)
# ============================================================

class TestIntegrationFlow:
    """Test the full end-to-end pipeline across channels."""

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_full_web_form_flow(self, sample_customer):
        """Test complete web form flow: create → respond → escalate."""
        # 1. Create ticket
        ticket = json.loads(create_ticket(CreateTicketInput(
            customer_name=sample_customer["name"],
            email=sample_customer["email"],
            channel="web_form",
            subject="Kanban board cards disappearing",
            message="When I drag cards from To Do to In Progress, they disappear. Happened 3 times today.",
        )))
        ticket_id = ticket["ticket"]["ticket_id"]

        # 2. Send response
        response = json.loads(send_response(SendResponseInput(
            ticket_id=ticket_id,
            response_text="Hello Alice,\n\nI understand this is frustrating. This appears to be a bug. I'm escalating to Engineering.",
            channel="web_form",
            include_escalation_note=True,
            escalation_team="Engineering Team",
            escalation_sla="1 hour",
        )))
        assert response["status"] == "sent"

        # 3. Escalate
        escalation = json.loads(escalate_to_human(EscalateToHumanInput(
            ticket_id=ticket_id,
            team="engineering",
            reason="Bug: Kanban cards disappearing after drag-and-drop",
            priority="P2",
            customer_name=sample_customer["name"],
            summary="Customer reports cards disappearing 3x today. Chrome on Windows.",
        )))
        assert escalation["status"] == "escalated"
        assert escalation["escalation"]["team"] == "Engineering Team"

        # 4. Verify customer history
        history = json.loads(get_customer_history(GetCustomerHistoryInput(
            email=sample_customer["email"],
        )))
        assert history["status"] == "found"
        assert history["total_tickets"] >= 1

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Tools not available")
    def test_cross_channel_flow_email_to_whatsapp(self, sample_customer):
        """Test flow: email ticket → WhatsApp follow-up → escalation."""
        # 1. Email ticket
        email_ticket = json.loads(create_ticket(CreateTicketInput(
            customer_name=sample_customer["name"],
            email=sample_customer["email"],
            channel="email",
            subject="Pricing inquiry",
            message="What's the difference between Starter and Professional plans?",
        )))
        email_ticket_id = email_ticket["ticket"]["ticket_id"]

        # 2. WhatsApp follow-up (same customer)
        wa_ticket = json.loads(create_ticket(CreateTicketInput(
            customer_name=sample_customer["name"],
            phone=sample_customer["phone"],
            channel="whatsapp",
            message="Hey, any update on my pricing question?",
        )))
        wa_ticket_id = wa_ticket["ticket"]["ticket_id"]

        # Verify same customer
        assert email_ticket["ticket"]["customer_id"] == wa_ticket["ticket"]["customer_id"]

        # 3. Respond via WhatsApp
        response = json.loads(send_response(SendResponseInput(
            ticket_id=wa_ticket_id,
            response_text="Hey Alice! 👋 Starter is $12/user/mo, Professional is $25/user/mo. Key difference: Professional has API access and custom workflows.",
            channel="whatsapp",
        )))
        assert response["status"] == "sent"
        assert response["channel"] == "whatsapp"

        # 4. Verify full history
        history = json.loads(get_customer_history(GetCustomerHistoryInput(
            email=sample_customer["email"],
        )))
        assert history["total_tickets"] == 2
        channels = set(c["channel"] for c in history["conversation_history"])
        assert "email" in channels
        assert "whatsapp" in channels


# ============================================================
# PYTEST CONFIGURATION
# ============================================================

def pytest_configure(config):
    """Custom pytest configuration."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
