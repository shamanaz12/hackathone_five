"""
TaskFlow AI Support Agent — Test Runner (Mock Mode)
CRM Digital FTE Factory Final Hackathon 5

This script tests the agent pipeline WITHOUT requiring:
- Real Kafka cluster
- Real Gmail API
- Real WhatsApp API
- Real PostgreSQL database

It uses in-memory stores and mock mode to validate the full pipeline.

Usage:
    python test_runner.py
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime, timezone

# ── Add project root to path ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Load settings ──
print("=" * 70)
print("TaskFlow AI Support Agent — Test Runner (Mock Mode)")
print("=" * 70)
print()

try:
    from production.config.settings import get_settings

    settings = get_settings()
    print("[OK] Settings loaded successfully")
    print(f"    Environment : {settings.environment}")
    print(f"    API Host    : {settings.api_host}:{settings.api_port}")
    print(f"    Support Email: {settings.support_email}")
    print(f"    OpenAI Model: {settings.openai_model}")
    print(f"    OpenAI Key  : {'***' + settings.openai_api_key[-4:] if settings.openai_api_key and len(settings.openai_api_key) > 4 else 'NOT SET (placeholder)'}")
    print()
except Exception as exc:
    print(f"[ERR] Failed to load settings: {exc}")
    print("    Continuing anyway...")
    print()

# ── Import agent tools ──
print("Loading agent tools...")
try:
    from production.agent.tools import (
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response,
        # Raw versions for direct calling
        search_kb_raw,
        create_ticket_raw,
        get_history_raw,
        escalate_raw,
        send_response_raw,
        SearchKnowledgeBaseInput,
        CreateTicketInput,
        GetCustomerHistoryInput,
        EscalateToHumanInput,
        SendResponseInput,
    )
    print("[OK] Agent tools loaded successfully")
    print()
except Exception as exc:
    print(f"[ERR] Failed to load agent tools: {exc}")
    print("    Make sure 'openai-agents' is installed OR the fallback decorator is working.")
    sys.exit(1)

# Map tool names to their raw functions for testing
TOOL_MAP = {
    "search_knowledge_base": search_kb_raw,
    "create_ticket": create_ticket_raw,
    "get_customer_history": get_history_raw,
    "escalate_to_human": escalate_raw,
    "send_response": send_response_raw,
}

# ── Test helpers ──
passed = 0
failed = 0


def test(name: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1


def run_tool(name: str, tool_fn, input_model, expected_status: str = "found"):
    """Run a tool and check its status field."""
    global passed, failed
    try:
        # If it's a FunctionTool, use the raw function with dict arguments
        if hasattr(tool_fn, "_is_agent_tool") or type(tool_fn).__name__ == "FunctionTool":
            # Get name from FunctionTool object
            fn_name = getattr(tool_fn, "name", None)
            raw_fn = TOOL_MAP.get(fn_name)
            if raw_fn:
                result_str = raw_fn(**input_model.model_dump())
            else:
                # Fallback: try calling it directly if it's just a function
                result_str = tool_fn(input_model)
        else:
            result_str = tool_fn(input_model)
            
        result = json.loads(result_str)
        status = result.get("status", "")
        if status == expected_status or (expected_status == "found" and status in ("found", "created", "sent", "escalated")):
            print(f"  [PASS] {name} — status={status}")
            passed += 1
            return result
        else:
            print(f"  [FAIL] {name} — expected status='{expected_status}', got '{status}'")
            failed += 1
            return result
    except Exception as exc:
        print(f"  [FAIL] {name} — exception: {exc}")
        failed += 1
        return None


# ============================================================
# TEST SUITE 1: Validation
# ============================================================
print("-" * 70)
print("TEST SUITE 1: Input Validation")
print("-" * 70)

# Topic validation
try:
    SearchKnowledgeBaseInput(query="test", topic="invalid_topic")
    test("Reject invalid topic", False)
except Exception:
    test("Reject invalid topic", True)

test("Accept valid topic", SearchKnowledgeBaseInput(query="test", topic="password_reset").topic == "password_reset")
test("Accept None topic", SearchKnowledgeBaseInput(query="test").topic is None)

# Channel validation
try:
    CreateTicketInput(customer_name="Test", message="Help", channel="slack")
    test("Reject invalid channel", False)
except Exception:
    test("Reject invalid channel", True)

test("Accept valid channel", CreateTicketInput(customer_name="Test", message="Help", channel="email").channel == "email")

# Email validation
try:
    CreateTicketInput(customer_name="Test", message="Help", channel="email", email="invalid")
    test("Reject invalid email", False)
except Exception:
    test("Reject invalid email", True)

# Escalation team validation
try:
    EscalateToHumanInput(ticket_id="T1", team="invalid_team", reason="test")
    test("Reject invalid escalation team", False)
except Exception:
    test("Reject invalid escalation team", True)

# Priority validation
try:
    EscalateToHumanInput(ticket_id="T1", team="security", reason="test", priority="P5")
    test("Reject invalid priority", False)
except Exception:
    test("Reject invalid priority", True)

print()

# ============================================================
# TEST SUITE 2: Knowledge Base Search
# ============================================================
print("-" * 70)
print("TEST SUITE 2: Knowledge Base Search")
print("-" * 70)

run_tool(
    "Search: password reset",
    search_knowledge_base,
    SearchKnowledgeBaseInput(query="I forgot my password and can't log in", topic="password_reset"),
)

run_tool(
    "Search: create project",
    search_knowledge_base,
    SearchKnowledgeBaseInput(query="How do I create a new project?", topic="create_project"),
)

run_tool(
    "Search: pricing",
    search_knowledge_base,
    SearchKnowledgeBaseInput(query="What are the pricing tiers?", topic="pricing"),
)

run_tool(
    "Search: no topic (auto-detect)",
    search_knowledge_base,
    SearchKnowledgeBaseInput(query="I can't reset my password, link expired"),
)

# FIX: Test invalid topic by catching the validation error (Pydantic validates on construction)
try:
    SearchKnowledgeBaseInput(query="help", topic="nonexistent")
    test("Reject invalid topic 'nonexistent'", False)
except Exception:
    test("Reject invalid topic 'nonexistent'", True)
    print("    [OK] Correctly rejected invalid topic")

# BONUS: Valid topic but query won't match any keywords
run_tool(
    "Search: valid topic but no matching content",
    search_knowledge_base,
    SearchKnowledgeBaseInput(query="something completely unrelated to projects", topic="kanban_board"),
    expected_status="not_found",
)

print()

# ============================================================
# TEST SUITE 3: Ticket Creation & Customer History
# ============================================================
print("-" * 70)
print("TEST SUITE 3: Ticket Creation & Customer History")
print("-" * 70)

ticket_result = run_tool(
    "Create ticket (email)",
    create_ticket,
    CreateTicketInput(
        customer_name="Alice Johnson",
        message="I can't log into my account. Password reset link expired.",
        channel="email",
        email="alice@example.com",
        subject="Login Issue",
    ),
    expected_status="created",
)

run_tool(
    "Create ticket (whatsapp)",
    create_ticket,
    CreateTicketInput(
        customer_name="Bob Smith",
        message="How do I add team members to my project?",
        channel="whatsapp",
        phone="+1 555 123 4567",
    ),
    expected_status="created",
)

run_tool(
    "Create ticket (web_form)",
    create_ticket,
    CreateTicketInput(
        customer_name="Charlie Brown",
        message="What is the pricing for Professional tier?",
        channel="web_form",
        email="charlie@example.com",
    ),
    expected_status="created",
)

# Customer history
if ticket_result:
    ticket_id = ticket_result["ticket"]["ticket_id"]
    customer_id = ticket_result["ticket"]["customer_id"]

    run_tool(
        "Get customer history (by email)",
        get_customer_history,
        GetCustomerHistoryInput(email="alice@example.com"),
    )

    run_tool(
        "Get customer history (by customer_id)",
        get_customer_history,
        GetCustomerHistoryInput(customer_id=customer_id),
    )

# Error case: no identifier
run_tool(
    "Get history: no identifier (error expected)",
    get_customer_history,
    GetCustomerHistoryInput(),
    expected_status="error",
)

print()

# ============================================================
# TEST SUITE 4: Escalation
# ============================================================
print("-" * 70)
print("TEST SUITE 4: Escalation to Human")
print("-" * 70)

if ticket_result:
    ticket_id = ticket_result["ticket"]["ticket_id"]

    escalation_result = run_tool(
        "Escalate to Security Team (P1)",
        escalate_to_human,
        EscalateToHumanInput(
            ticket_id=ticket_id,
            team="security",
            reason="Customer account potentially compromised",
            priority="P1",
            customer_name="Alice Johnson",
            summary="Cannot login, password reset not working, possible security issue",
        ),
        expected_status="escalated",
    )

    # Escalate non-existent ticket
    run_tool(
        "Escalate: invalid ticket (error expected)",
        escalate_to_human,
        EscalateToHumanInput(
            ticket_id="TICKET-99999",
            team="engineering",
            reason="Test",
        ),
        expected_status="error",
    )

print()

# ============================================================
# TEST SUITE 5: Response Sending
# ============================================================
print("-" * 70)
print("TEST SUITE 5: Response Sending")
print("-" * 70)

if ticket_result:
    ticket_id = ticket_result["ticket"]["ticket_id"]

    run_tool(
        "Send email response",
        send_response,
        SendResponseInput(
            ticket_id=ticket_id,
            response_text="Hi Alice, I've reset your password. Please check your email for the new reset link.",
            channel="email",
            agent_name="TaskFlow AI Agent",
        ),
        expected_status="sent",
    )

    run_tool(
        "Send WhatsApp response",
        send_response,
        SendResponseInput(
            ticket_id=ticket_id,
            response_text="Hi! To add team members, go to your project -> Team tab -> Invite Members.",
            channel="whatsapp",
            agent_name="TaskFlow AI Agent",
        ),
        expected_status="sent",
    )

    run_tool(
        "Send response with escalation note",
        send_response,
        SendResponseInput(
            ticket_id=ticket_id,
            response_text="I understand this is urgent.",
            channel="email",
            agent_name="TaskFlow AI Agent",
            include_escalation_note=True,
            escalation_team="Security Team",
            escalation_sla="30 minutes",
        ),
        expected_status="sent",
    )

    # Error case: non-existent ticket
    run_tool(
        "Send response: invalid ticket (error expected)",
        send_response,
        SendResponseInput(
            ticket_id="TICKET-99999",
            response_text="Test",
            channel="email",
        ),
        expected_status="error",
    )

print()

# ============================================================
# TEST SUITE 6: Full Pipeline Simulation
# ============================================================
print("-" * 70)
print("TEST SUITE 6: Full Pipeline Simulation")
print("-" * 70)

print("  Simulating: Customer sends email -> AI searches KB -> creates ticket -> responds")
print()

# Step 1: Customer sends support request
print("  Step 1: Customer sends email")
customer_message = "I forgot my password and the reset link expired. I need to access my account urgently."
print(f"    Message: {customer_message}")

# Step 2: AI searches knowledge base
print("  Step 2: AI searches knowledge base")
kb_result = json.loads(search_kb_raw(
    query=customer_message, topic="password_reset"
))
test("KB search found relevant content", kb_result.get("status") == "found")
if kb_result.get("status") == "found":
    print(f"    Found {kb_result['results_count']} result(s)")

# Step 3: AI creates ticket
print("  Step 3: AI creates ticket")
ticket_result = json.loads(create_ticket_raw(
    customer_name="Sarah Wilson",
    message=customer_message,
    channel="email",
    email="sarah@example.com",
    subject="Password Reset Issue",
))
test("Ticket created", ticket_result.get("status") == "created")
if ticket_result.get("status") == "created":
    ticket_id = ticket_result["ticket"]["ticket_id"]
    print(f"    Ticket ID: {ticket_id}")

# Step 4: AI generates response
print("  Step 4: AI sends response")
response_result = json.loads(send_response_raw(
    ticket_id=ticket_id,
    response_text=(
        "Hi Sarah, I understand you're having trouble with password reset. "
        "Here's what you can do:\n\n"
        "1. Go to the login page and click 'Forgot Password?'\n"
        "2. Enter your email address\n"
        "3. Check your inbox (and spam folder) for the reset link\n"
        "4. The link expires after 1 hour\n\n"
        "If you still don't receive it, I can manually trigger a reset for you."
    ),
    channel="email",
    agent_name="TaskFlow AI Agent",
))
test("Response sent", response_result.get("status") == "sent")

# Step 5: Check customer history
print("  Step 5: Verify customer history")
history_result = json.loads(get_history_raw(
    email="sarah@example.com"
))
test("Customer history retrieved", history_result.get("status") == "found")
if history_result.get("status") == "found":
    print(f"    Total tickets: {history_result['total_tickets']}")
    print(f"    Total interactions: {history_result['total_interactions']}")

print()

# ============================================================
# SUMMARY
# ============================================================
print("=" * 70)
print(f"TEST RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 70)

if failed == 0:
    print()
    print("[SUCCESS] All tests passed! Your agent tools are working correctly.")
    print()
    print("Next steps:")
    print("  1. Start the FastAPI server:  uvicorn production.api.main:app --reload --port 8000")
    print("  2. Open API docs:            http://localhost:8000/api/docs")
    print("  3. Test health check:        curl http://localhost:8000/health")
    print("  4. Create a ticket:          curl -X POST http://localhost:8000/api/tickets -H 'Content-Type: application/json' -d '{...}'")
    print()
else:
    print()
    print(f"[WARNING] {failed} test(s) failed. Review the output above to identify issues.")
    print()

sys.exit(0 if failed == 0 else 1)
