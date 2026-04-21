"""
TaskFlow AI Support Agent Prototype v2
CRM Digital FTE Factory Final Hackathon 5

Pipeline: Receive -> Normalize -> Classify -> Search -> Respond -> Escalate
New in v2: Conversation Memory, Sentiment Tracking, Resolution Status, Cross-Channel Continuity
"""

import re
import json
import sys
import io
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timedelta, timezone
from enum import Enum

# Force UTF-8 output for Windows console compatibility
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ============================================================
# ENUMS
# ============================================================

class ResolutionStatus(Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class SentimentLabel(Enum):
    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


# ============================================================
# 1. KNOWLEDGE BASE (embedded from product-docs.md)
# ============================================================

KNOWLEDGE_BASE = {
    "password_reset": {
        "keywords": [
            "password", "reset", "forgot password", "login", "sign in",
            "can't log in", "cannot log in", "locked out", "access my account",
            "reset link", "expired", "not received", "didn't receive"
        ],
        "priority_keywords": {
            "P1": ["locked", "compromised", "hack", "unauthorized", "too many attempts"],
            "P2": ["not received", "expired", "still haven't", "waiting", "minutes"],
        },
        "response_template": {
            "steps": [
                "Go to the login page and click 'Forgot Password?'",
                "Enter your registered email address",
                "Check your inbox (and spam folder) for the reset email -- the link is valid for 1 hour",
                "Click the link and create a new password (8+ characters, 1 uppercase, 1 number, 1 special character)",
            ],
            "troubleshooting": [
                "If the reset email hasn't arrived after 5 minutes, check your spam folder",
                "Reset links expire after 1 hour -- request a new one if expired",
                "After 10 failed attempts, accounts are temporarily locked for security",
            ],
            "support_action": "I can manually trigger a fresh reset email if needed.",
        },
    },
    "create_project": {
        "keywords": [
            "create project", "new project", "add project", "+ new project",
            "can't create", "project limit", "can't find", "where is",
            "start a project", "make a project"
        ],
        "priority_keywords": {
            "P2": [],
            "P3": ["how", "where", "can't find", "don't see", "limit reached"],
        },
        "response_template": {
            "steps": [
                "Log in to TaskFlow",
                "Look for the '+ New Project' button at the top right of your dashboard",
                "Fill in the project name (required), description, template, visibility, and dates",
                "Click 'Create Project'",
            ],
            "troubleshooting": [
                "Free tier: max 3 projects -- upgrade or archive old ones to create more",
                "Starter/Professional/Enterprise: unlimited projects",
                "If the button isn't visible, try refreshing your browser or clearing cache",
            ],
            "support_action": "I can check your account to see if there's a hidden or archived project.",
        },
    },
    "invite_team_members": {
        "keywords": [
            "invite", "team member", "add member", "add user", "send invite",
            "invitation", "didn't receive", "not received", "bulk import",
            "role", "admin", "member", "viewer", "change role",
            "invite limit", "member limit"
        ],
        "priority_keywords": {
            "P2": [],
            "P3": ["didn't receive", "not received", "how to", "change role", "bulk", "limit"],
        },
        "response_template": {
            "steps": [
                "Open the project and click the 'Team' tab",
                "Click 'Invite Members'",
                "Enter email address(es) -- comma-separated for multiple invites",
                "Select a role: Admin (full control), Member (create/edit tasks), or Viewer (read-only)",
                "Click 'Send Invites'",
            ],
            "troubleshooting": [
                "Invitations expire after 7 days",
                "Free tier: max 5 members | Starter: 50 | Professional: 200 | Enterprise: unlimited",
                "Bulk CSV import is available on Professional and Enterprise tiers (max 500 per upload)",
                "To change a role: go to Team tab -> click dropdown next to member -> select new role",
            ],
            "support_action": "I can resend invitations or check your tier limits.",
        },
    },
    "kanban_board": {
        "keywords": [
            "kanban", "board", "drag", "drop", "column", "card",
            "slow", "loading", "not visible", "disappeared", "missing",
            "export", "pdf", "custom column", "add column",
            "WIP limit", "filter", "shortcut"
        ],
        "priority_keywords": {
            "P2": ["slow", "bug", "disappear", "not working", "error", "broken", "15", "20 seconds"],
            "P3": ["how to", "export", "custom", "add column", "shortcut", "filter"],
        },
        "response_template": {
            "steps": [
                "The Kanban board is the default project view with columns: Backlog, To Do, In Progress, In Review, Done",
                "Drag and drop cards between columns to update their status",
                "To add/remove/rename columns: click Settings -> 'Manage Columns'",
            ],
            "troubleshooting": [
                "Cards not draggable? Check browser compatibility, disable extensions, and refresh",
                "Slow loading? Large boards take time -- use filters to reduce visible cards",
                "Missing cards? Check filters and verify the task wasn't archived or deleted",
                "Export to PDF: available from the project menu -> Export -> PDF",
            ],
            "support_action": "If cards are disappearing, this may be a bug -- I can escalate to Engineering.",
        },
    },
    "pricing": {
        "keywords": [
            "pricing", "plan", "tier", "upgrade", "downgrade", "cost",
            "billing", "charge", "refund", "subscription",
            "free trial", "trial expired", "enterprise", "SSO",
            "on-premise", "nonprofit", "discount", "switch", "cancel"
        ],
        "priority_keywords": {
            "P1": ["legal", "threaten", "churn"],
            "P2": ["charged twice", "duplicate", "billing error", "enterprise", "SSO", "on-premise", "800", "100+"],
            "P4": ["how much", "difference", "discount", "nonprofit", "compare"],
        },
        "response_template": {
            "steps": [],
            "pricing_info": (
                "Free: $0/mo -- 5 members, 3 projects, basic Kanban\n"
                "Starter: $12/user/mo -- unlimited projects, 50 members, time tracking, integrations\n"
                "Professional: $25/user/mo -- 200 members, custom workflows, API, advanced reporting, bulk import\n"
                "Enterprise: Custom pricing -- unlimited members, SSO, on-premise, dedicated support, 99.99% SLA"
            ),
            "billing_details": [
                "Monthly or annual billing (save 20% on annual)",
                "14-day free trial for Starter and Professional (no credit card required)",
                "30-day money-back guarantee",
                "Upgrade/downgrade anytime with prorated billing",
                "Nonprofit discount: 50% off all paid tiers",
                "Data is preserved when you downgrade -- features revert at next billing cycle",
            ],
            "support_action": "I can connect you with Sales for Enterprise inquiries or Billing for refund requests.",
        },
    },
}

# ============================================================
# 2. ESCALATION RULES
# ============================================================

ESCALATION_TEAMS = {
    "P1": {"team": "Security Team", "email": "security@techcorp.com", "sla": "30 minutes"},
    "P2_engineering": {"team": "Engineering Team", "email": "eng-support@techcorp.internal", "sla": "1 hour"},
    "P2_billing": {"team": "Billing Team", "email": "billing@techcorp.com", "sla": "1 hour"},
    "P2_sales": {"team": "Sales Team", "email": "sales@techcorp.com", "sla": "2 hours"},
    "P2_support": {"team": "Support Team", "email": "support@techcorp.com", "sla": "1 hour"},
    "P3": {"team": "Support Team", "email": "support-queue@techcorp.internal", "sla": "4 hours"},
}

# ============================================================
# 3. BRAND VOICE CONFIG
# ============================================================

BRAND_VOICE = {
    "email": {
        "greeting": "Hi {name},",
        "sign_off": "\nBest regards,\nThe TaskFlow Support Team",
        "use_emojis": False,
        "style": "paragraphs",
        "max_length": "long",
    },
    "whatsapp": {
        "greeting": "Hey {name}! [wave]",
        "sign_off": "\nHope that helps! [smile]",
        "use_emojis": True,
        "style": "short",
        "max_length": "short",
    },
    "web_form": {
        "greeting": "Hello {name},",
        "sign_off": "\nThank you for contacting TaskFlow Support.\nBest regards,\nThe TaskFlow Team",
        "use_emojis": False,
        "style": "paragraphs",
        "max_length": "medium",
    },
}

# Emoji map (kept separate so we can strip them for non-emoji channels)
EMOJI_MAP = {
    "[wave]": "\U0001F44B",
    "[smile]": "\U0001F60A",
    "[1]": "1\ufe0f\u20e3",
    "[2]": "2\ufe0f\u20e3",
    "[3]": "3\ufe0f\u20e3",
    "[4]": "4\ufe0f\u20e3",
    "[5]": "5\ufe0f\u20e3",
    "[tip]": "\U0001F4A1",
}


# ============================================================
# 4. DATA CLASSES
# ============================================================

@dataclass
class ConversationTurn:
    """A single exchange in a conversation."""
    turn_number: int
    timestamp: str
    channel: str
    customer_message: str
    agent_response: str
    topic: str
    priority: str
    sentiment_score: int
    resolution_status: str


@dataclass
class CustomerProfile:
    """Persistent profile for a customer across channels."""
    customer_id: str            # derived from email or phone
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tier: str = "unknown"       # free, starter, professional, enterprise
    channels_seen: list = field(default_factory=list)
    total_tickets: int = 0
    resolved_tickets: int = 0
    escalated_tickets: int = 0
    sentiment_history: list = field(default_factory=list)  # list of (timestamp, score)
    topic_history: list = field(default_factory=list)      # list of (timestamp, topic)
    last_contact: str = ""
    created_at: str = ""


@dataclass
class CustomerTicket:
    ticket_id: str
    channel: str
    customer_name: str
    message: str
    email: Optional[str] = None
    phone: Optional[str] = None
    subject: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class AgentResponse:
    ticket_id: str
    channel: str
    topic: str
    priority: str
    response_text: str
    escalation_needed: bool
    escalation_team: str = ""
    escalation_sla: str = ""
    ai_attempt: int = 1
    resolution_status: str = "new"
    sentiment: str = "neutral"
    sentiment_score: int = 0
    is_follow_up: bool = False
    cross_channel_switch: bool = False
    previous_channel: str = ""
    conversation_summary: str = ""


# ============================================================
# 5. SENTIMENT ANALYZER
# ============================================================

class SentimentAnalyzer:
    """Rule-based sentiment scoring from -2 (very negative) to +2 (very positive)."""

    POSITIVE_WORDS = {
        "love": 2, "great": 1, "thanks": 1, "thank": 1, "appreciate": 1,
        "awesome": 2, "excellent": 2, "happy": 1, "good": 1, "nice": 1,
        "helpful": 1, "perfect": 2, "wonderful": 2, "fantastic": 2,
    }

    NEGATIVE_WORDS = {
        "hate": -2, "terrible": -2, "awful": -2, "worst": -2, "horrible": -2,
        "frustrated": -1, "frustrating": -1, "annoying": -1, "angry": -2,
        "upset": -1, "disappointed": -1, "disappointing": -1, "broken": -1,
        "useless": -2, "waste": -1, "ridiculous": -2, "unacceptable": -2,
        "still": -0.5, "not": -0.5, "never": -1, "no": -0.3,
    }

    URGENCY_PENALTY = {
        "asap": -0.5, "urgent": -0.5, "critical": -0.5,
        "immediately": -0.5, "right now": -0.5,
    }

    @classmethod
    def analyze(cls, message: str) -> tuple[int, str]:
        """Return (score, label) for the message."""
        lower = message.lower()
        words = re.findall(r'\b\w+\b', lower)

        score = 0.0
        for w in words:
            if w in cls.POSITIVE_WORDS:
                score += cls.POSITIVE_WORDS[w]
            if w in cls.NEGATIVE_WORDS:
                score += cls.NEGATIVE_WORDS[w]

        # Check multi-word phrases
        for phrase, penalty in cls.URGENCY_PENALTY.items():
            if phrase in lower:
                score += penalty

        # Clamp to -2..+2
        score = max(-2, min(2, round(score)))

        label_map = {
            -2: "very_negative",
            -1: "negative",
            0: "neutral",
            1: "positive",
            2: "very_positive",
        }
        return score, label_map.get(score, "neutral")


# ============================================================
# 6. CONVERSATION MEMORY
# ============================================================

class ConversationMemory:
    """Stores conversation history per customer and enables cross-channel continuity."""

    def __init__(self):
        # customer_id -> list of ConversationTurn
        self.conversations: dict[str, list[ConversationTurn]] = {}
        # email/phone -> customer_id mapping
        self.identity_map: dict[str, str] = {}
        # customer_id -> CustomerProfile
        self.profiles: dict[str, CustomerProfile] = {}

    def resolve_customer(self, ticket: CustomerTicket) -> str:
        """Resolve a ticket to a customer ID using email or phone. Creates profile if new."""
        customer_id = None

        # Try email first
        if ticket.email:
            customer_id = self.identity_map.get(ticket.email.lower())

        # Try phone
        if not customer_id and ticket.phone:
            customer_id = self.identity_map.get(ticket.phone)

        # New customer
        if not customer_id:
            customer_id = f"CUST-{len(self.profiles) + 1:04d}"
            now = datetime.now(timezone.utc).isoformat()
            self.profiles[customer_id] = CustomerProfile(
                customer_id=customer_id,
                name=ticket.customer_name,
                email=ticket.email,
                phone=ticket.phone,
                created_at=now,
            )

        # Update identity map
        if ticket.email and ticket.email.lower() not in self.identity_map:
            self.identity_map[ticket.email.lower()] = customer_id
        if ticket.phone and ticket.phone not in self.identity_map:
            self.identity_map[ticket.phone] = customer_id

        # Update profile with latest info
        profile = self.profiles[customer_id]
        if ticket.email and not profile.email:
            profile.email = ticket.email
        if ticket.phone and not profile.phone:
            profile.phone = ticket.phone

        return customer_id

    def get_conversation(self, customer_id: str) -> list[ConversationTurn]:
        return self.conversations.get(customer_id, [])

    def get_last_turn(self, customer_id: str) -> Optional[ConversationTurn]:
        turns = self.conversations.get(customer_id, [])
        return turns[-1] if turns else None

    def detect_channel_switch(self, customer_id: str, new_channel: str) -> tuple[bool, str]:
        """Check if customer is contacting from a different channel than before."""
        profile = self.profiles.get(customer_id)
        if not profile:
            return False, ""
        previous = profile.channels_seen[-1] if profile.channels_seen else ""
        switched = previous != "" and previous != new_channel
        return switched, previous

    def detect_follow_up(self, customer_id: str, new_topic: str) -> bool:
        """Check if this is a follow-up on a recent topic."""
        turns = self.conversations.get(customer_id, [])
        if not turns:
            return False
        last_topic = turns[-1].topic
        return last_topic == new_topic

    def record_turn(self, customer_id: str, turn: ConversationTurn):
        if customer_id not in self.conversations:
            self.conversations[customer_id] = []
        self.conversations[customer_id].append(turn)

        # Update profile
        profile = self.profiles[customer_id]
        profile.total_tickets += 1
        if turn.channel not in profile.channels_seen:
            profile.channels_seen.append(turn.channel)
        profile.last_contact = turn.timestamp
        profile.sentiment_history.append((turn.timestamp, turn.sentiment_score))
        profile.topic_history.append((turn.timestamp, turn.topic))

        if turn.resolution_status == "resolved":
            profile.resolved_tickets += 1
        if turn.resolution_status == "escalated":
            profile.escalated_tickets += 1

    def get_conversation_summary(self, customer_id: str) -> str:
        """Generate a brief summary of the customer's conversation history."""
        turns = self.conversations.get(customer_id, [])
        if not turns:
            return "No prior conversation history."

        profile = self.profiles.get(customer_id)
        channels = ", ".join(profile.channels_seen) if profile else "unknown"
        topics = [t.topic for t in turns]
        unique_topics = list(dict.fromkeys(topics))  # preserve order, deduplicate
        avg_sentiment = sum(t.sentiment_score for t in turns) / len(turns) if turns else 0

        summary_parts = [
            f"Customer has {len(turns)} prior interaction(s) across channels: {channels}.",
            f"Topics discussed: {', '.join(unique_topics)}.",
            f"Average sentiment: {avg_sentiment:+.1f} (range: -2 very negative to +2 very positive).",
        ]

        if turns:
            last = turns[-1]
            summary_parts.append(
                f"Last contact: {last.timestamp} via {last.channel} "
                f"about {last.topic} (status: {last.resolution_status})."
            )

        return " ".join(summary_parts)

    def get_sentiment_trend(self, customer_id: str) -> str:
        """Describe sentiment trajectory."""
        history = self.profiles.get(customer_id, CustomerProfile("", "")).sentiment_history
        if len(history) < 2:
            return "Insufficient data for trend."

        scores = [s for _, s in history]
        if scores[-1] > scores[0]:
            return "Improving -- sentiment has gotten better over time."
        elif scores[-1] < scores[0]:
            return "Declining -- sentiment has worsened over time. Consider priority handling."
        else:
            return "Stable -- sentiment has remained consistent."


# ============================================================
# 7. NORMALIZER
# ============================================================

class MessageNormalizer:
    """Clean and standardize incoming messages."""

    @staticmethod
    def normalize(message: str) -> str:
        text = message.strip().lower()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'^(hi|hey|hello|good morning|good afternoon|good evening)\b[,! ]*', '', text).strip()
        text = re.sub(r'\b(please|pls|could you|can you|would you)\b', '', text).strip()
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        return text

    @staticmethod
    def detect_urgency(message: str) -> list[str]:
        indicators = []
        lower = message.lower()
        if any(w in lower for w in ["asap", "urgent", "critical", "immediately", "right now"]):
            indicators.append("time_sensitive")
        if any(w in lower for w in ["frustrating", "frustrated", "annoying", "angry", "upset"]):
            indicators.append("negative_emotion")
        if any(w in lower for w in ["love", "great", "thanks", "thank", "appreciate"]):
            indicators.append("positive_sentiment")
        if any(w in lower for w in ["presentation", "deadline", "sprint", "launch", "demo"]):
            indicators.append("business_impact")
        # Follow-up indicators
        if any(w in lower for w in ["still", "still not", "still haven't", "any update", "following up", "as i mentioned"]):
            indicators.append("follow_up")
        # Human request
        if any(w in lower for w in ["speak to someone", "talk to a person", "human agent", "real person", "supervisor"]):
            indicators.append("human_request")
        return indicators

    @staticmethod
    def extract_numbers(message: str) -> list[int]:
        return [int(n) for n in re.findall(r'\b(\d+)\b', message)]


# ============================================================
# 8. CLASSIFIER
# ============================================================

class TicketClassifier:
    """Classify ticket topic and priority using keyword matching."""

    @staticmethod
    def classify_topic(normalized: str) -> str:
        scores = {}
        for topic, config in KNOWLEDGE_BASE.items():
            score = sum(1 for kw in config["keywords"] if kw in normalized)
            if score > 0:
                scores[topic] = score
        if not scores:
            return "unknown"
        return max(scores, key=scores.get)

    @staticmethod
    def classify_priority(normalized: str, topic: str, urgency: list[str]) -> str:
        if topic == "unknown":
            return "P3"

        config = KNOWLEDGE_BASE.get(topic, {})
        priority_keywords = config.get("priority_keywords", {})

        for kw in priority_keywords.get("P1", []):
            if kw in normalized:
                return "P1"
        if "time_sensitive" in urgency and "business_impact" in urgency:
            if any(w in normalized for w in ["locked", "can't access", "cannot access"]):
                return "P1"

        for kw in priority_keywords.get("P2", []):
            if kw in normalized:
                return "P2"
        if topic == "pricing" and any(w in normalized for w in ["charged twice", "duplicate", "refund", "billing error"]):
            return "P2"
        if topic == "pricing" and any(w in normalized for w in ["enterprise", "sso", "on-premise", "100+", "800"]):
            return "P2"
        if any(w in normalized for w in ["bug", "not working", "broken", "error", "disappear"]):
            return "P2"

        for kw in priority_keywords.get("P4", []):
            if kw in normalized:
                return "P4"

        return "P3"


# ============================================================
# 9. RESPONSE GENERATOR (with memory awareness)
# ============================================================

class ResponseGenerator:
    """Generate channel-aware responses with conversation context."""

    def __init__(self):
        self.normalizer = MessageNormalizer()

    def generate(
        self,
        ticket: CustomerTicket,
        topic: str,
        priority: str,
        urgency: list[str],
        memory: ConversationMemory,
        customer_id: str,
    ) -> str:
        voice = BRAND_VOICE.get(ticket.channel, BRAND_VOICE["email"])
        config = KNOWLEDGE_BASE.get(topic)

        if not config:
            return self._fallback_response(ticket, voice)

        parts = []

        # Greeting
        parts.append(self._apply_emojis(voice["greeting"].format(name=ticket.customer_name.split()[0]), voice))

        # Cross-channel acknowledgment
        switched, prev_channel = memory.detect_channel_switch(customer_id, ticket.channel)
        if switched:
            parts.append(
                f"I see you previously reached out via {prev_channel.replace('_', ' ')}. "
                f"I have your full conversation history here, so no need to repeat yourself."
            )

        # Follow-up acknowledgment
        last_turn = memory.get_last_turn(customer_id)
        if "follow_up" in urgency and last_turn:
            parts.append(
                f"Thanks for following up on this. I can see we last discussed this on "
                f"{last_turn.timestamp} via {last_turn.channel}. Let me check the latest status."
            )
        else:
            parts.append(self._acknowledge(ticket.message, urgency, topic, voice))

        # Provide solution
        if topic == "pricing":
            parts.append(self._pricing_response(config, voice))
        else:
            parts.append(self._step_response(config, voice))

        # Sentiment-aware closing
        sentiment_score, _ = SentimentAnalyzer.analyze(ticket.message)
        if sentiment_score <= -1:
            parts.append("I know this has been frustrating -- I'm committed to getting this resolved for you.")
        else:
            parts.append(self._proactive_help(topic, voice))

        # Sign-off
        parts.append(self._apply_emojis(voice["sign_off"], voice))

        return "\n\n".join(parts)

    def _apply_emojis(self, text: str, voice: dict) -> str:
        """Replace emoji placeholders if channel supports them."""
        if voice.get("use_emojis"):
            for placeholder, emoji in EMOJI_MAP.items():
                text = text.replace(placeholder, emoji)
        else:
            # Strip placeholders
            for placeholder in EMOJI_MAP:
                text = text.replace(placeholder, "")
            text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _acknowledge(self, original: str, urgency: list[str], topic: str, voice: dict) -> str:
        if "negative_emotion" in urgency:
            return "I understand this is frustrating, and I'm here to help get this sorted for you."
        if "time_sensitive" in urgency or "business_impact" in urgency:
            return "I can see this is time-sensitive -- let me help you resolve this quickly."
        if "positive_sentiment" in urgency:
            return "Thanks for the kind words! Happy to help with this."
        return "Thanks for reaching out -- I can help with that."

    def _step_response(self, config: dict, voice: dict) -> str:
        steps = config["response_template"].get("steps", [])
        troubleshooting = config["response_template"].get("troubleshooting", [])

        if voice["style"] == "short":
            step_text = "\n".join(
                f"[{i+1}] {s}" for i, s in enumerate(steps[:3])
            )
            if troubleshooting:
                step_text += f"\n\n[tip] {troubleshooting[0]}"
            return step_text
        else:
            text = "Here's what to do:\n"
            for i, step in enumerate(steps, 1):
                text += f"{i}. {step}\n"
            if troubleshooting:
                text += "\nA few things to keep in mind:\n"
                for t in troubleshooting[:2]:
                    text += f"- {t}\n"
            return text

    def _pricing_response(self, config: dict, voice: dict) -> str:
        pricing_info = config["response_template"].get("pricing_info", "")
        billing_details = config["response_template"].get("billing_details", [])

        if voice["style"] == "short":
            return f"Here are our plans:\n\n{pricing_info}"
        else:
            text = f"Here's an overview of our plans:\n\n{pricing_info}"
            if billing_details:
                text += "\n\nBilling details:\n"
                for d in billing_details:
                    text += f"- {d}\n"
            return text

    def _proactive_help(self, topic: str, voice: dict) -> str:
        proactive = {
            "password_reset": "If you still don't receive the reset email within 5 minutes, let me know and I'll investigate further.",
            "create_project": "Once your project is set up, you can start adding tasks and inviting team members right away.",
            "invite_team_members": "Your team members will receive an invitation email -- if they don't see it, ask them to check their spam folder.",
            "kanban_board": "You can also try keyboard shortcuts: press 'N' to create a new task, or '/' to search.",
            "pricing": "If you'd like, I can connect you with our Sales team for a personalized recommendation.",
        }
        return proactive.get(topic, "Let me know if there's anything else I can help with!")

    def _fallback_response(self, ticket: CustomerTicket, voice: dict) -> str:
        parts = [voice["greeting"].format(name=ticket.customer_name.split()[0])]
        parts.append("Thanks for reaching out. I want to make sure I give you the best help possible.")
        parts.append("Could you share a bit more detail about what you're experiencing? This will help me find the right solution for you.")
        parts.append("In the meantime, you can browse our help center at www.techcorp.com/help for guides on common topics.")
        parts.append(self._apply_emojis(voice["sign_off"], voice))
        return "\n\n".join(parts)


# ============================================================
# 10. ESCALATION DECIDER
# ============================================================

class EscalationDecider:
    """Decide if and where to escalate based on priority, topic, attempt count, and sentiment."""

    @staticmethod
    def decide(
        priority: str,
        topic: str,
        ai_attempt: int,
        urgency: list[str],
        sentiment_score: int,
        sentiment_trend: str,
    ) -> dict:
        result = {
            "escalate": False,
            "team": "",
            "sla": "",
            "reason": "",
        }

        # P1: immediate escalation
        if priority == "P1":
            team_info = ESCALATION_TEAMS["P1"]
            result.update({
                "escalate": True,
                "team": team_info["team"],
                "sla": team_info["sla"],
                "reason": "Critical issue -- account locked or security concern",
            })
            return result

        # Human request
        if "human_request" in urgency:
            result.update({
                "escalate": True,
                "team": "Support Team",
                "sla": "1 hour",
                "reason": "Customer requested human agent",
            })
            return result

        # Sentiment-driven escalation: very negative + declining trend
        if sentiment_score <= -2 and "Declining" in sentiment_trend:
            result.update({
                "escalate": True,
                "team": "Customer Success",
                "sla": "1 hour",
                "reason": "Sentiment critically negative and declining -- proactive escalation",
            })
            return result

        # P2: escalate after 1 AI attempt
        if priority == "P2":
            if ai_attempt >= 1:
                if topic == "kanban_board":
                    team_info = ESCALATION_TEAMS["P2_engineering"]
                elif topic == "pricing":
                    team_info = ESCALATION_TEAMS["P2_sales"]
                else:
                    team_info = ESCALATION_TEAMS["P2_support"]
                result.update({
                    "escalate": True,
                    "team": team_info["team"],
                    "sla": team_info["sla"],
                    "reason": f"P2 issue -- {topic.replace('_', ' ')} -- AI attempted resolution",
                })
            return result

        # P3: escalate after 2 AI attempts
        if priority == "P3":
            if ai_attempt >= 2:
                team_info = ESCALATION_TEAMS["P3"]
                result.update({
                    "escalate": True,
                    "team": team_info["team"],
                    "sla": team_info["sla"],
                    "reason": f"P3 issue -- {topic.replace('_', ' ')} -- AI attempted twice",
                })
            return result

        return result


# ============================================================
# 11. MAIN AGENT PIPELINE (with memory)
# ============================================================

class TaskFlowAgent:
    """Main AI agent with conversation memory and cross-channel continuity."""

    def __init__(self):
        self.memory = ConversationMemory()
        self.normalizer = MessageNormalizer()
        self.classifier = TicketClassifier()
        self.generator = ResponseGenerator()
        self.decider = EscalationDecider()
        self.sentiment = SentimentAnalyzer()

    def process(self, ticket: CustomerTicket, ai_attempt: int = 1) -> AgentResponse:
        """Full pipeline with memory, sentiment, and cross-channel awareness."""

        # Step 0: Resolve customer identity
        customer_id = self.memory.resolve_customer(ticket)

        # Step 1: Normalize
        normalized = self.normalizer.normalize(ticket.message)
        urgency = self.normalizer.detect_urgency(ticket.message)

        # Step 2: Classify
        topic = self.classifier.classify_topic(normalized)
        priority = self.classifier.classify_priority(normalized, topic, urgency)

        # Step 3: Sentiment analysis
        sentiment_score, sentiment_label = self.sentiment.analyze(ticket.message)
        sentiment_trend = self.memory.get_sentiment_trend(customer_id)

        # Step 4: Detect context
        is_follow_up = self.memory.detect_follow_up(customer_id, topic)
        channel_switched, prev_channel = self.memory.detect_channel_switch(customer_id, ticket.channel)
        conversation_summary = self.memory.get_conversation_summary(customer_id)

        # Step 5: Generate response (memory-aware)
        response_text = self.generator.generate(
            ticket, topic, priority, urgency, self.memory, customer_id
        )

        # Step 6: Decide escalation
        escalation = self.decider.decide(
            priority, topic, ai_attempt, urgency, sentiment_score, sentiment_trend
        )

        # Determine resolution status
        if escalation["escalate"]:
            resolution_status = ResolutionStatus.ESCALATED.value
        elif is_follow_up and ai_attempt >= 2:
            resolution_status = ResolutionStatus.RESOLVED.value
        else:
            resolution_status = ResolutionStatus.IN_PROGRESS.value

        # Step 7: Record in memory
        now = ticket.timestamp or datetime.now(timezone.utc).isoformat()
        turn = ConversationTurn(
            turn_number=len(self.memory.get_conversation(customer_id)) + 1,
            timestamp=now,
            channel=ticket.channel,
            customer_message=ticket.message,
            agent_response=response_text,
            topic=topic,
            priority=priority,
            sentiment_score=sentiment_score,
            resolution_status=resolution_status,
        )
        self.memory.record_turn(customer_id, turn)

        return AgentResponse(
            ticket_id=ticket.ticket_id,
            channel=ticket.channel,
            topic=topic,
            priority=priority,
            response_text=response_text,
            escalation_needed=escalation["escalate"],
            escalation_team=escalation["team"],
            escalation_sla=escalation["sla"],
            ai_attempt=ai_attempt,
            resolution_status=resolution_status,
            sentiment=sentiment_label,
            sentiment_score=sentiment_score,
            is_follow_up=is_follow_up,
            cross_channel_switch=channel_switched,
            previous_channel=prev_channel,
            conversation_summary=conversation_summary,
        )

    def get_customer_profile(self, ticket: CustomerTicket) -> Optional[CustomerProfile]:
        """Retrieve the full profile for a customer."""
        customer_id = self.memory.resolve_customer(ticket)
        return self.memory.profiles.get(customer_id)


# ============================================================
# 12. TEST EXAMPLES
# ============================================================

def print_separator(title: str):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_response(r: AgentResponse):
    print(f"  Topic:              {r.topic}")
    print(f"  Priority:           {r.priority}")
    print(f"  Sentiment:          {r.sentiment} ({r.sentiment_score:+d})")
    print(f"  Resolution Status:  {r.resolution_status}")
    print(f"  Follow-up:          {r.is_follow_up}")
    print(f"  Channel Switch:     {r.cross_channel_switch} (from: {r.previous_channel})")
    print(f"  Escalation:         {r.escalation_needed}")
    if r.escalation_needed:
        print(f"    -> Team: {r.escalation_team} (SLA: {r.escalation_sla})")
    print(f"\n  Conversation Context: {r.conversation_summary}")
    print(f"\n  Response:\n  {'-' * 40}")
    for line in r.response_text.split("\n"):
        print(f"  {line}")
    print(f"  {'-' * 40}")


def run_tests():
    agent = TaskFlowAgent()

    # ---------------------------------------------------------------
    # TEST 1: Normal -- Email, Password Reset (P2, first contact)
    # ---------------------------------------------------------------
    print_separator("TEST 1: Normal -- Email, Password Reset (P2, first contact)")

    t1 = CustomerTicket(
        ticket_id="TKT-001",
        channel="email",
        customer_name="Alice Johnson",
        email="alice.j@startupco.com",
        message="Hi, I've been trying to reset my password for the past hour. I keep clicking the link in the email but it says 'This link has expired.' I just requested it 5 minutes ago! Please help, I have a client presentation tomorrow and need to access my TaskFlow projects urgently.",
        timestamp="2026-04-07T09:00:00Z",
    )
    r1 = agent.process(t1)
    print_response(r1)

    # ---------------------------------------------------------------
    # TEST 2: Follow-up -- Same customer, same topic, via WhatsApp
    # ---------------------------------------------------------------
    print_separator("TEST 2: Follow-up -- Same customer, channel switch (email -> whatsapp)")

    t2 = CustomerTicket(
        ticket_id="TKT-001-FU",
        channel="whatsapp",
        customer_name="Alice Johnson",
        email="alice.j@startupco.com",
        phone="+1 555 123 4567",
        message="Hey, I still haven't received the password reset email. It's been 15 minutes now. Any update on this?",
        timestamp="2026-04-07T09:20:00Z",
    )
    r2 = agent.process(t2, ai_attempt=2)
    print_response(r2)

    # Show updated profile
    profile = agent.get_customer_profile(t2)
    if profile:
        print(f"\n  Customer Profile: {profile.name} ({profile.customer_id})")
        print(f"    Channels seen:    {profile.channels_seen}")
        print(f"    Total tickets:    {profile.total_tickets}")
        print(f"    Sentiment trend:  {agent.memory.get_sentiment_trend(profile.customer_id)}")

    # ---------------------------------------------------------------
    # TEST 3: Channel Switch -- New customer starts on web_form, then follows up on email
    # ---------------------------------------------------------------
    print_separator("TEST 3: Channel Switch -- Web Form -> Email, Kanban Board bug (P2)")

    t3a = CustomerTicket(
        ticket_id="TKT-015",
        channel="web_form",
        customer_name="Fatima Al-Rashid",
        email="fatima.ar@consulting.sa",
        message="When I drag a card from 'To Do' to 'In Progress', it sometimes disappears from the board entirely. It's still in the system (I can find it via search) but it's not visible in any column. This has happened 3 times today. Using Chrome on Windows.",
        timestamp="2026-04-07T12:30:00Z",
    )
    r3a = agent.process(t3a)
    print_response(r3a)

    # Follow-up via email (channel switch)
    print_separator("TEST 3b: Follow-up -- Same customer switches to email")

    t3b = CustomerTicket(
        ticket_id="TKT-015-FU",
        channel="email",
        customer_name="Fatima Al-Rashid",
        email="fatima.ar@consulting.sa",
        message="Hi, following up on my earlier report about cards disappearing on the Kanban board. This is still happening and it's affecting our team's workflow. Is there an update?",
        timestamp="2026-04-07T14:00:00Z",
    )
    r3b = agent.process(t3b, ai_attempt=2)
    print_response(r3b)

    # Show profile
    profile3 = agent.get_customer_profile(t3b)
    if profile3:
        print(f"\n  Customer Profile: {profile3.name} ({profile3.customer_id})")
        print(f"    Channels seen:    {profile3.channels_seen}")
        print(f"    Total tickets:    {profile3.total_tickets}")
        print(f"    Escalated:        {profile3.escalated_tickets}")
        print(f"    Sentiment trend:  {agent.memory.get_sentiment_trend(profile3.customer_id)}")

    # ---------------------------------------------------------------
    # TEST 4: Normal -- WhatsApp, Pricing Inquiry (P4, new customer)
    # ---------------------------------------------------------------
    print_separator("TEST 4: Normal -- WhatsApp, Pricing Inquiry (P4, new customer)")

    t4 = CustomerTicket(
        ticket_id="TKT-005",
        channel="whatsapp",
        customer_name="Sophie Chen",
        phone="+61 412 345 678",
        message="Hi! Quick question - what's the difference between Starter and Professional plans? We're a team of 8 and not sure which one to pick. Also do you offer nonprofit discounts?",
        timestamp="2026-04-07T14:20:00Z",
    )
    r4 = agent.process(t4)
    print_response(r4)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print_separator("AGENT MEMORY SUMMARY")
    print(f"  Total customers tracked:  {len(agent.memory.profiles)}")
    print(f"  Total conversations:      {sum(len(v) for v in agent.memory.conversations.values())}")
    print(f"  Identity mappings:        {len(agent.memory.identity_map)}")
    print()
    for cid, profile in agent.memory.profiles.items():
        print(f"  {cid}: {profile.name}")
        print(f"    Email: {profile.email} | Phone: {profile.phone}")
        print(f"    Channels: {profile.channels_seen}")
        print(f"    Tickets: {profile.total_tickets} (resolved: {profile.resolved_tickets}, escalated: {profile.escalated_tickets})")
        print(f"    Sentiment history: {profile.sentiment_history}")
        print()


if __name__ == "__main__":
    run_tests()
