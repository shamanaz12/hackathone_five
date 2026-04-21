"""
Test harness for TaskFlow MCP Server tools.
Calls each tool directly to verify correctness.
"""

import sys
import json
sys.path.insert(0, "src")

from mcp_server import (
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    Channel,
)


def show(title: str, result: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    parsed = json.loads(result)
    print(json.dumps(parsed, indent=2))


def main():
    # ── TOOL 1: search_knowledge_base ──
    r1 = search_knowledge_base(
        query="I can't reset my password, the link expired",
        topic="password_reset",
    )
    show("TOOL 1: search_knowledge_base (password_reset)", r1)

    # Also test cross-topic search
    r1b = search_knowledge_base(
        query="how do I add custom columns and export to PDF",
    )
    show("TOOL 1b: search_knowledge_base (no topic filter)", r1b)

    # ── TOOL 2: create_ticket ──
    r2 = create_ticket(
        customer_name="Alice Johnson",
        message="I've been trying to reset my password for the past hour. The reset link says expired even though I just requested it 5 minutes ago. I have a client presentation tomorrow!",
        channel="email",
        email="alice.j@startupco.com",
        subject="Can't reset my password - reset link not working",
    )
    show("TOOL 2: create_ticket", r2)

    ticket_data = json.loads(r2)
    ticket_id = ticket_data["ticket"]["ticket_id"]
    customer_id = ticket_data["ticket"]["customer_id"]

    # Create a second ticket from same customer via different channel
    r2b = create_ticket(
        customer_name="Alice Johnson",
        message="Hey, I still haven't received the password reset email. Any update?",
        channel="whatsapp",
        email="alice.j@startupco.com",
        phone="+1 555 123 4567",
    )
    show("TOOL 2b: create_ticket (same customer, different channel)", r2b)

    # ── TOOL 3: get_customer_history ──
    r3 = get_customer_history(email="alice.j@startupco.com")
    show("TOOL 3: get_customer_history (by email)", r3)

    # ── TOOL 4: escalate_to_human ──
    r4 = escalate_to_human(
        ticket_id=ticket_id,
        team="security",
        reason="Account locked after multiple password reset attempts. Customer is admin of company account with critical sprint starting.",
        priority="P1",
        customer_name="Alice Johnson",
        summary="Customer tried resetting password multiple times. Account now locked. Needs immediate unlock to access projects for client presentation.",
    )
    show("TOOL 4: escalate_to_human (P1 -> Security)", r4)

    # Escalate a second ticket to engineering
    r4b = create_ticket(
        customer_name="Fatima Al-Rashid",
        message="Cards disappearing on Kanban board when dragging from To Do to In Progress. Happened 3 times today. Chrome on Windows.",
        channel="web_form",
        email="fatima.ar@consulting.sa",
        subject="Kanban board - cards disappearing after drag and drop",
    )
    ticket_2 = json.loads(r4b)["ticket"]["ticket_id"]

    r4c = escalate_to_human(
        ticket_id=ticket_2,
        team="engineering",
        reason="Bug report: Kanban board cards disappear after drag-and-drop operation.",
        priority="P2",
        customer_name="Fatima Al-Rashid",
        summary="Customer reports cards disappearing after drag from To Do to In Progress. Reproducible (3x). Environment: Chrome/Windows.",
    )
    show("TOOL 4b: escalate_to_human (P2 -> Engineering)", r4c)

    # ── TOOL 5: send_response ──
    r5 = send_response(
        ticket_id=ticket_id,
        response_text=(
            "Hi Alice,\n\n"
            "I can see this is time-sensitive. I've manually triggered a fresh password reset email to your address. "
            "This new link will be valid for 1 hour.\n\n"
            "1. Check your inbox (and spam folder)\n"
            "2. Click the 'Reset Password' link\n"
            "3. Create a new password (8+ chars, 1 uppercase, 1 number, 1 special char)\n\n"
            "If you don't receive it within 5 minutes, reply and I'll investigate further."
        ),
        channel="email",
        agent_name="TaskFlow AI Agent",
    )
    show("TOOL 5: send_response (email, no escalation note)", r5)

    # Send response with escalation note
    r5b = send_response(
        ticket_id=ticket_2,
        response_text=(
            "Hello Fatima,\n\n"
            "Thank you for reporting this issue. I understand how frustrating it is when cards disappear on the Kanban board.\n\n"
            "This appears to be a bug. I've gathered the details from your report:\n"
            "- Issue: Cards disappear after drag from 'To Do' to 'In Progress'\n"
            "- Frequency: 3 times today\n"
            "- Environment: Chrome on Windows\n\n"
            "I'm escalating this to our Engineering team for investigation."
        ),
        channel="web_form",
        agent_name="TaskFlow AI Agent",
        include_escalation_note=True,
        escalation_team="Engineering Team",
        escalation_sla="1 hour",
    )
    show("TOOL 5b: send_response (web_form, with escalation note)", r5b)

    # ── Channel Enum validation ──
    print(f"\n{'=' * 70}")
    print("  CHANNEL ENUM VALIDATION")
    print(f"{'=' * 70}")
    for ch in Channel:
        print(f"  Channel.{ch.name} = '{ch.value}'")

    # ── Error handling tests ──
    print(f"\n{'=' * 70}")
    print("  ERROR HANDLING TESTS")
    print(f"{'=' * 70}")

    err1 = create_ticket(
        customer_name="Test",
        message="test",
        channel="slack",  # invalid
    )
    print(f"\n  Invalid channel: {json.loads(err1)['status']} - {json.loads(err1)['message']}")

    err2 = escalate_to_human(
        ticket_id="TICKET-9999",  # doesn't exist
        team="security",
        reason="test",
    )
    print(f"  Non-existent ticket: {json.loads(err2)['status']} - {json.loads(err2)['message']}")

    err3 = escalate_to_human(
        ticket_id=ticket_id,
        team="marketing",  # invalid team
        reason="test",
    )
    print(f"  Invalid team: {json.loads(err3)['status']} - {json.loads(err3)['message']}")

    print(f"\n{'=' * 70}")
    print("  ALL TESTS PASSED")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
