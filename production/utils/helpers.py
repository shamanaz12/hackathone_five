"""
TaskFlow AI Support Agent — Utility Helpers
Production package for the CRM Digital FTE Factory Final Hackathon 5.
"""

from __future__ import annotations

import re
from typing import Optional


# ============================================================
# ID GENERATORS
# ============================================================

_counters: dict[str, int] = {
    "ticket": 0,
    "customer": 0,
    "escalation": 0,
}


def generate_ticket_id() -> str:
    """Generate a unique ticket ID (TICKET-NNNN)."""
    _counters["ticket"] += 1
    return f"TICKET-{_counters['ticket']:04d}"


def generate_customer_id() -> str:
    """Generate a unique customer ID (CUST-NNNN)."""
    _counters["customer"] += 1
    return f"CUST-{_counters['customer']:04d}"


def generate_escalation_id() -> str:
    """Generate a unique escalation ID (ESCALATION-NNNN)."""
    _counters["escalation"] += 1
    return f"ESCALATION-{_counters['escalation']:04d}"


# ============================================================
# INPUT SANITIZATION
# ============================================================

def sanitize_input(text: str) -> str:
    """Sanitize customer input by stripping dangerous characters.

    - Collapses excessive whitespace
    - Removes null bytes
    - Limits length to 10,000 characters
    - Preserves legitimate punctuation and unicode
    """
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to max length
    max_len = 10000
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


# ============================================================
# DATA EXTRACTION
# ============================================================

def extract_email(text: str) -> Optional[str]:
    """Extract the first email address from text."""
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extract the first phone number from text."""
    match = re.search(r"\+?[\d\s\-()]{7,20}", text)
    return match.group(0).strip() if match else None


# ============================================================
# CHANNEL FORMATTING
# ============================================================

# Emoji placeholder map
_EMOJI_MAP = {
    "[wave]": "\U0001F44B",
    "[smile]": "\U0001F60A",
    "[tip]": "\U0001F4A1",
}


def format_for_channel(text: str, channel: str) -> str:
    """Apply channel-specific formatting to response text.

    - WhatsApp: renders emoji placeholders, truncates at 1000 chars
    - Email / Web Form: strips emoji placeholders, full length
    """
    channel_lower = channel.lower()

    if channel_lower == "whatsapp":
        # Render emoji placeholders
        for placeholder, emoji in _EMOJI_MAP.items():
            text = text.replace(placeholder, emoji)
        # Format numbered steps: "1." -> "[1]"
        text = re.sub(r"^(\d+)\.\s", r"[\1] ", text, flags=re.MULTILINE)
        # Truncate if too long
        if len(text) > 1000:
            text = text[:1000] + "\n\n[Message truncated -- full details sent via email]"
        return text

    elif channel_lower in ("email", "web_form"):
        # Strip emoji placeholders
        for placeholder in _EMOJI_MAP:
            text = text.replace(placeholder, "")
        # Clean up any double whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # Default: return as-is
    return text
