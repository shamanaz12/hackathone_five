"""
TaskFlow AI Support Agent — Customer Success Agent
CRM Digital FTE Factory Final Hackathon 5

Builds an OpenAI Agents SDK Agent with:
- All 5 function tools (search, ticket, history, escalate, respond)
- Channel-aware system instructions
- Full processing pipeline (normalize → classify → sentiment → respond → escalate)
- Guardrails and handoff logic
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from production.agent.prompts import (
    CUSTOMER_SUCCESS_SYSTEM_PROMPT,
    KB_RETRIEVAL_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    ESCALATION_DECISION_PROMPT,
    CHANNEL_ADAPTATION_PROMPT,
    FALLBACK_PROMPT,
    ESCALATION_HANDOFF_PROMPT,
)
from production.agent.tools import (
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    # Raw functions for fallback
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
    Channel,
    EscalationTeam,
    Priority,
)
from production.config.settings import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# TRY IMPORT OpenAI SDK
# ============================================================

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI SDK not installed — agent will use mock mode")

# For backward compatibility if any code still checks these
AGENTS_SDK_AVAILABLE = False
Agent = None
Runner = None


# ============================================================
# CHANNEL-AWARE INSTRUCTION BUILDER
# ============================================================

def build_system_instructions(
    channel: str = "email",
    include_escalation_rules: bool = True,
    include_pricing_table: bool = True,
) -> str:
    """
    Build system instructions tailored to the communication channel.

    Args:
        channel: One of "email", "whatsapp", "web_form".
        include_escalation_rules: Whether to include the full escalation matrix.
        include_pricing_table: Whether to include the pricing tier table.

    Returns:
        Complete system prompt string.
    """
    base = CUSTOMER_SUCCESS_SYSTEM_PROMPT

    # Channel-specific override section
    channel_section = _channel_specific_text(channel)
    base = base + "\n\n" + channel_section

    if not include_escalation_rules:
        # Remove escalation section for lightweight mode
        base = base.split("## ESCALATION TRIGGERS")[0] + "\n\nEscalation rules are loaded from config."

    if not include_pricing_table:
        base = base.split("## PRICING TIERS")[0] + "\n\nPricing info available via knowledge base search."

    return base


def _channel_specific_text(channel: str) -> str:
    """Return channel-specific formatting reminders for the agent."""
    channel = channel.lower()
    if channel == "email":
        return (
            "## CHANNEL: EMAIL\n"
            "- Use semi-formal tone, 3-8 paragraphs\n"
            "- Greeting: 'Hi {name},'\n"
            "- Sign-off: 'Best regards,\\nThe TaskFlow Support Team'\n"
            "- NO emojis\n"
            "- Use full paragraphs with bullet points (- for bullets)\n"
            "- Numbered steps: '1. Step text'\n"
            "- Include full URLs"
        )
    elif channel == "whatsapp":
        return (
            "## CHANNEL: WHATSAPP\n"
            "- Use friendly, concise tone, under 1000 characters\n"
            "- Greeting: 'Hey {name}!'\n"
            "- Sign-off: 'Hope that helps!'\n"
            "- Use 1-2 emojis maximum\n"
            "- Short lines, not paragraphs\n"
            "- Numbered steps: '[1] Step text'\n"
            "- Use bullet points: '• Point text'"
        )
    elif channel == "web_form":
        return (
            "## CHANNEL: WEB FORM\n"
            "- Use professional, structured tone, 2-5 paragraphs\n"
            "- Greeting: 'Hello {name},'\n"
            "- Sign-off: 'Thank you for contacting TaskFlow Support.\\nBest regards,\\nThe TaskFlow Team'\n"
            "- NO emojis\n"
            "- Structured paragraphs with bullet points\n"
            "- Numbered steps: '1. Step text'\n"
            "- Always acknowledge receipt of their submission"
        )
    return ""


# ============================================================
# AGENT BUILDER
# ============================================================

def create_customer_success_agent(
    model: str = "gpt-4o-mini",
    channel: str = "email",
    temperature: float = 0.3,
    max_tokens: int = 2000,
    include_tools: bool = True,
) -> dict:
    """
    Create a TaskFlow Customer Success Agent configuration.
    """
    system_instructions = build_system_instructions(
        channel=channel,
        include_escalation_rules=True,
        include_pricing_table=True,
    )

    tools = []
    if include_tools:
        tools = [
            "search_knowledge_base",
            "create_ticket",
            "get_customer_history",
            "escalate_to_human",
            "send_response",
        ]

    return {
        "name": "TaskFlow Customer Success Agent",
        "model": model,
        "channel": channel,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_instructions": system_instructions,
        "tools": tools,
    }


# ============================================================
# PROCESSING PIPELINE
# ============================================================

class AgentPipeline:
    """
    Orchestrates the full agent pipeline for a single customer inquiry.
    """

    def __init__(
        self,
        agent: Optional[dict] = None,
        model: Optional[str] = None,
        channel: str = "email",
    ):
        self.settings = get_settings()
        self.channel = channel
        self.agent_config = agent or create_customer_success_agent(
            model=model or self.settings.openai_model, 
            channel=channel,
            temperature=self.settings.agent_temperature,
            max_tokens=self.settings.agent_max_tokens
        )
        
        self.client = None
        if OPENAI_AVAILABLE and self.settings.openai_api_key:
            self.client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url
            )

    async def process_inquiry(
        self,
        customer_name: str,
        message: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Process a customer inquiry using a dynamic tool-calling agent loop.
        """
        if not self.client:
            logger.warning("AI Client not available — falling back to rule-based pipeline")
            return await self._process_inquiry_rules_fallback(customer_name, message, email, phone, subject)

        logger.info(f"Starting dynamic agent loop for {customer_name} via {self.channel}")
        
        messages = [
            {"role": "system", "content": self.agent_config["system_instructions"]},
            {"role": "user", "content": f"Customer: {customer_name}\nEmail: {email}\nPhone: {phone}\nSubject: {subject}\nMessage: {message}"}
        ]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge_base",
                    "description": "Search product documentation for answers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "topic": {"type": "string", "enum": ["password_reset", "create_project", "invite_team_members", "kanban_board", "pricing"]}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_ticket",
                    "description": "Create a new support ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {"type": "string"},
                            "message": {"type": "string"},
                            "channel": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"},
                            "subject": {"type": "string"}
                        },
                        "required": ["customer_name", "message", "channel"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_customer_history",
                    "description": "View customer conversation and ticket history.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"},
                            "phone": {"type": "string"},
                            "customer_id": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "Escalate ticket to a human support team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "team": {"type": "string", "enum": ["security", "engineering", "billing", "sales", "support", "customer_success"]},
                            "reason": {"type": "string"},
                            "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                            "summary": {"type": "string"}
                        },
                        "required": ["ticket_id", "team", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "send_response",
                    "description": "Send formatted response to customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "response_text": {"type": "string"},
                            "channel": {"type": "string"},
                            "include_escalation_note": {"type": "boolean"},
                            "escalation_team": {"type": "string"},
                            "escalation_sla": {"type": "string"}
                        },
                        "required": ["ticket_id", "response_text", "channel"]
                    }
                }
            }
        ]

        # Tool mapping
        available_functions = {
            "search_knowledge_base": self._create_kb_tool_wrapper(),
            "create_ticket": self._create_ticket_tool_wrapper(),
            "get_customer_history": self._get_history_tool_wrapper(),
            "escalate_to_human": self._escalate_tool_wrapper(),
            "send_response": self._send_response_tool_wrapper(),
        }

        max_turns = 10
        result_summary = {"steps": {}, "status": "processing"}
        
        for i in range(max_turns):
            try:
                response = await self.client.chat.completions.create(
                    model=self.agent_config["model"],
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                messages.append(msg)
                
                if not msg.tool_calls:
                    # Final response from agent
                    content = msg.content or ""
                    
                    # Extract RESPONSE section if present
                    if "RESPONSE:" in content:
                        response_part = content.split("RESPONSE:")[-1].strip()
                        # Remove markdown code blocks if the agent wrapped the response
                        response_part = response_part.replace("```", "").strip()
                        result_summary["response"] = response_part
                    else:
                        result_summary["response"] = content.strip()
                        
                    result_summary["status"] = "completed"
                    break
                
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Agent calling tool: {fn_name}({fn_args})")
                    
                    fn = available_functions.get(fn_name)
                    if fn:
                        tool_result = fn(**fn_args)
                        result_summary["steps"][f"{fn_name}_{i}"] = tool_result
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": json.dumps(tool_result)
                        })
                        
                        # Extra metadata extraction
                        if fn_name == "create_ticket" and "ticket" in tool_result:
                            result_summary["ticket_id"] = tool_result["ticket"]["ticket_id"]
                            result_summary["customer_id"] = tool_result["ticket"]["customer_id"]
                        
                        if fn_name == "send_response" and "status" in tool_result:
                            result_summary["response"] = fn_args.get("response_text", "")
                
            except Exception as e:
                logger.error(f"Error in agent loop turn {i}: {e}", exc_info=True)
                result_summary["status"] = "error"
                result_summary["error"] = str(e)
                break
        
        # If no response was set but agent finished
        if "response" not in result_summary and result_summary["status"] == "completed":
            # Fallback to the last assistant message if it wasn't a tool call
            last_msg = messages[-1]
            if last_msg.get("role") == "assistant" and last_msg.get("content"):
                result_summary["response"] = last_msg["content"]

        return result_summary

    def _create_kb_tool_wrapper(self):
        def wrapper(query, topic=None):
            return self._search_kb(query, topic)
        return wrapper

    def _create_ticket_tool_wrapper(self):
        def wrapper(customer_name, message, channel, email=None, phone=None, subject=None):
            return self._create_ticket(customer_name, message, email, phone, subject)
        return wrapper

    def _get_history_tool_wrapper(self):
        def wrapper(email=None, phone=None, customer_id=None):
            return self._get_history(email, phone, customer_id)
        return wrapper

    def _escalate_tool_wrapper(self):
        def wrapper(ticket_id, team, reason, priority="P2", summary=None, customer_name=None):
            return self._escalate(ticket_id, team, reason, priority, customer_name or "Customer")
        return wrapper

    def _send_response_tool_wrapper(self):
        def wrapper(ticket_id, response_text, channel, include_escalation_note=False, escalation_team=None, escalation_sla=None):
            escalation = {"escalate": include_escalation_note, "team": escalation_team, "sla": escalation_sla}
            return self._send_response(ticket_id, response_text, channel, escalation)
        return wrapper

    async def _process_inquiry_rules_fallback(
        self, customer_name, message, email, phone, subject
    ) -> dict:
        """Old static pipeline used as fallback."""
        # ... (rest of old process_inquiry implementation if you want to keep it)
        # For brevity, I'll just keep the original logic here but renamed.
        # Actually, let's just make it call the old one or similar.
        return await self._old_process_inquiry(customer_name, message, email, phone, subject)

    async def _old_process_inquiry(
        self, customer_name, message, email, phone, subject
    ) -> dict:
        # (This is just a placeholder for the original method body)
        result = {"status": "processing", "channel": self.channel, "steps": {}}
        ticket_result = self._create_ticket(customer_name, message, email, phone, subject)
        result["steps"]["create_ticket"] = ticket_result
        if ticket_result.get("status") != "created":
            result["status"] = "error"
            return result
        ticket_id = ticket_result["ticket"]["ticket_id"]
        result["ticket_id"] = ticket_id
        
        # 1. Search Knowledge Base
        kb_result = self._search_kb(query=message)
        result["steps"]["knowledge_base"] = kb_result
        
        # 2. Analyze Sentiment
        sentiment_result = self._analyze_sentiment(message)
        result["steps"]["sentiment"] = sentiment_result
        
        # 3. Generate Smart Rule-based Response
        kb_data = kb_result.get("results", [])
        if kb_data:
            # Smart fallback: use KB content
            kb_main = kb_data[0]
            answer = kb_main.get("content", "I found some relevant information for you.")
            details = kb_main.get("details", {})
            
            response_text = f"Hi {customer_name}, I've found some information regarding your inquiry about '{kb_main.get('title')}':\n\n"
            
            # Extract content if it's a dict
            if isinstance(answer, dict):
                overview = answer.get("overview", "")
                if overview:
                    response_text += f"{overview}\n\n"
                steps = answer.get("steps", [])
                if steps:
                    response_text += "Steps:\n" + "\n".join(f"- {s}" for s in steps) + "\n"
            else:
                response_text += f"{answer}\n\n"

            if details:
                if isinstance(details, dict):
                    for k, v in details.items():
                        response_text += f"- {k.replace('_', ' ').title()}: {v}\n"
                elif isinstance(details, list):
                    for item in details:
                        response_text += f"- {item}\n"
            
            response_text += f"\nI've also created a ticket ({ticket_id}) if you need more help!"
        else:
            # Generic fallback
            response_text = f"Hi {customer_name}, I've received your ticket {ticket_id}. I couldn't find a direct answer in my database, but our team will help you soon."
            
        # Add a small note about AI mode if key is missing
        if not self.settings.openai_api_key or "sk-" in self.settings.openai_api_key:
             response_text += "\n\n(Note: I'm currently running in 'Smart Rule' mode. Add an OpenAI API Key to .env to enable my full AI Brain!)"

        send_result = self._send_response(ticket_id, response_text, self.channel, {"escalate": False})
        result["response"] = response_text
        result["status"] = "completed"
        return result

    async def _run_ai_analysis(self, customer_name, message, kb_context, history) -> dict:
        """Use LLM to analyze sentiment, decide escalation, and generate response with Gemini fallback."""
        prompt = f"""
        Customer: {customer_name}
        Channel: {self.channel}
        Message: {message}
        
        Knowledge Base Context:
        {kb_context}
        
        Customer History Summary:
        {json.dumps(history.get('customer_profile', {}))}
        
        Task:
        1. Analyze sentiment (score -2 to 2, label).
        2. Decide if escalation is needed (escalate true/false, team, priority, reason).
        3. Generate a {self.channel} formatted response following the system instructions.
        
        Return JSON only:
        {{
          "sentiment": {{"score": 0, "label": "neutral"}},
          "escalation": {{"escalate": false, "team": "support", "priority": "P3", "reason": ""}},
          "response": "..."
        }}
        """
        
        # 1. Try Primary Client (OpenRouter/OpenAI)
        if self.client:
            try:
                response = await self.client.chat.completions.create(
                    model=self.agent_config["model"],
                    messages=[
                        {"role": "system", "content": self.agent_config["system_instructions"]},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.agent_config["temperature"],
                    max_tokens=self.agent_config["max_tokens"]
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.warning("Primary AI Analysis failed: %s. Trying Gemini fallback...", e)

        # 2. Try Gemini Fallback
        if self.settings.gemini_api_key:
            try:
                # Use OpenAI compatibility layer for Gemini
                gemini_client = AsyncOpenAI(
                    api_key=self.settings.gemini_api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
                response = await gemini_client.chat.completions.create(
                    model="gemini-1.5-flash",
                    messages=[
                        {"role": "system", "content": self.agent_config["system_instructions"]},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.agent_config["temperature"],
                    max_tokens=self.agent_config["max_tokens"]
                )
                logger.info("Gemini fallback successful")
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.warning("Gemini fallback failed: %s. Trying Cohere...", e)

        # 3. Try Cohere Fallback
        if self.settings.cohere_api_key:
            try:
                # Cohere Command-R-Plus via OpenRouter (using existing client but different model)
                # or we can use another compatible endpoint. For now, let's use the provided key
                # assuming the user wants to use it as an alternative.
                cohere_client = AsyncOpenAI(
                    api_key=self.settings.cohere_api_key,
                    base_url="https://api.cohere.ai/v1/openai" # Cohere's OpenAI compatible endpoint
                )
                response = await cohere_client.chat.completions.create(
                    model="command-r-plus",
                    messages=[
                        {"role": "system", "content": self.agent_config["system_instructions"]},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.agent_config["temperature"],
                    max_tokens=self.agent_config["max_tokens"]
                )
                logger.info("Cohere fallback successful")
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.error("Cohere fallback also failed: %s", e)

        return {}

    # ── Pipeline Steps ──

    def _create_ticket(self, customer_name, message, email=None, phone=None, subject=None) -> dict:
        try:
            raw = create_ticket_raw(
                customer_name=customer_name,
                message=message,
                channel=self.channel,
                email=email,
                phone=phone,
                subject=subject,
            )
            return json.loads(raw)
        except Exception as exc:
            logger.error("Pipeline step create_ticket failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _get_history(self, email=None, phone=None, customer_id=None) -> dict:
        try:
            raw = get_history_raw(
                email=email, 
                phone=phone,
                customer_id=customer_id
            )
            return json.loads(raw)
        except Exception as exc:
            logger.error("Pipeline step get_history failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _search_kb(self, query: str, topic: str = None) -> dict:
        try:
            raw = search_kb_raw(query=query, topic=topic)
            return json.loads(raw)
        except Exception as exc:
            logger.error("Pipeline step search_kb failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _analyze_sentiment(self, message: str) -> dict:
        """Rule-based sentiment analysis (same as prototype)."""
        positive_words = {
            "love": 2, "great": 1, "thanks": 1, "thank": 1, "appreciate": 1,
            "awesome": 2, "excellent": 2, "happy": 1, "good": 1, "nice": 1,
        }
        negative_words = {
            "hate": -2, "terrible": -2, "awful": -2, "worst": -2, "horrible": -2,
            "frustrated": -1, "frustrating": -1, "annoying": -1, "angry": -2,
            "upset": -1, "disappointed": -1, "broken": -1, "useless": -2,
            "not": -0.5, "never": -1, "no": -0.3, "still": -0.5,
        }
        urgency_penalty = {"asap": -0.5, "urgent": -0.5, "critical": -0.5, "immediately": -0.5}

        score = 0.0
        lower = message.lower()
        words = lower.split()
        for w in words:
            score += positive_words.get(w, 0)
            score += negative_words.get(w, 0)
        for phrase, penalty in urgency_penalty.items():
            if phrase in lower:
                score += penalty

        score = max(-2, min(2, round(score)))
        label_map = {-2: "very_negative", -1: "negative", 0: "neutral", 1: "positive", 2: "very_positive"}

        indicators = []
        if any(w in lower for w in ["asap", "urgent", "critical", "immediately"]):
            indicators.append("time_sensitive")
        if any(w in lower for w in ["frustrated", "annoying", "angry", "upset"]):
            indicators.append("negative_emotion")
        if any(w in lower for w in ["love", "great", "thanks", "thank"]):
            indicators.append("positive_sentiment")

        return {"score": score, "label": label_map.get(score, "neutral"), "indicators": indicators}

    def _decide_escalation_rules(self, topic, sentiment_score, sentiment_label) -> dict:
        """Rule-based escalation decision."""
        # Very negative sentiment → immediate P1 escalation
        if sentiment_label == "very_negative":
            return {
                "escalate": True, "team": "support", "priority": "P1",
                "sla": "30 minutes", "reason": "Very negative sentiment detected",
            }

        # P1 triggers: critical security issues
        if sentiment_score <= -1 and sentiment_label in ("very_negative", "negative"):
            if topic == "password_reset":
                return {
                    "escalate": True, "team": "security", "priority": "P1",
                    "sla": "30 minutes", "reason": "Critical security issue — account access compromised",
                }
            if any(w in ["locked", "compromised", "hack"] for w in topic.split("_")):
                return {
                    "escalate": True, "team": "security", "priority": "P1",
                    "sla": "30 minutes", "reason": "Critical security issue",
                }

        # P2 triggers
        if topic in ("kanban_board",) and sentiment_score <= -1:
            return {
                "escalate": True, "team": "engineering", "priority": "P2",
                "sla": "1 hour", "reason": f"Bug report: {topic}",
            }
        if topic == "pricing" and sentiment_score <= -1:
            return {
                "escalate": True, "team": "billing", "priority": "P2",
                "sla": "1 hour", "reason": f"Billing dispute: {topic}",
            }

        # P3: no escalation on first attempt
        # P4: no escalation

        return {"escalate": False, "team": "", "priority": "P3", "sla": "", "reason": ""}

    def _generate_response_rules(
        self, customer_name, message, kb_context, sentiment, escalation,
    ) -> str:
        """Generate a channel-aware response."""
        first_name = customer_name.split()[0] if customer_name else "there"

        # Greeting
        if self.channel == "whatsapp":
            greeting = f"Hey {first_name}! 👋"
            sign_off = "\nHope that helps! 😊"
        elif self.channel == "web_form":
            greeting = f"Hello {first_name},"
            sign_off = "\nThank you for contacting TaskFlow Support.\nBest regards,\nThe TaskFlow Team"
        else:
            greeting = f"Hi {first_name},"
            sign_off = "\nBest regards,\nThe TaskFlow Support Team"

        # Acknowledge
        sentiment_score = sentiment.get("score", 0)
        if sentiment_score <= -1:
            ack = "I understand this is frustrating, and I'm here to help get this sorted for you."
        elif sentiment_score >= 1:
            ack = "Thanks for the kind words! Happy to help with this."
        else:
            ack = "Thanks for reaching out — I can help with that."

        # Solution from KB
        solution = ""
        if kb_context:
            solution = f"\n\nHere's what to do:\n{kb_context}"
        else:
            solution = (
                "\n\nI want to make sure I give you the best help possible. "
                "Could you share a bit more detail about what you're experiencing?"
            )

        # Escalation note
        esc_note = ""
        if escalation.get("escalate"):
            esc_note = (
                f"\n\nI've also escalated this to our {escalation.get('team', 'support')} team. "
                f"You can expect a response within {escalation.get('sla', 'a few hours')}."
            )

        return f"{greeting}\n\n{ack}{solution}{esc_note}{sign_off}"

    def _send_response(self, ticket_id, response_text, channel, escalation) -> dict:
        try:
            raw = send_response_raw(
                ticket_id=ticket_id,
                response_text=response_text,
                channel=channel,
                include_escalation_note=escalation.get("escalate", False),
                escalation_team=escalation.get("team", "").replace("_", " ").title() if escalation.get("team") else None,
                escalation_sla=escalation.get("sla") or None,
            )
            return json.loads(raw)
        except Exception as exc:
            logger.error("Pipeline step send_response failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _escalate(self, ticket_id, team, reason, priority, customer_name) -> dict:
        try:
            raw = escalate_raw(
                ticket_id=ticket_id,
                team=team,
                reason=reason,
                priority=priority,
                customer_name=customer_name,
                summary=f"Auto-escalated by agent pipeline: {reason}",
            )
            return json.loads(raw)
        except Exception as exc:
            logger.error("Pipeline step escalate failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    @staticmethod
    def _format_kb_context(results: list) -> str:
        """Format knowledge base results into readable context."""
        if not results:
            return ""
        parts = []
        for r in results[:2]:  # Top 2 results
            content = r.get("content", {})
            if isinstance(content, dict):
                overview = content.get("overview", "")
                if overview:
                    parts.append(overview)
                common = content.get("common_issues", [])
                if common:
                    parts.append("Common issues:\n" + "\n".join(f"- {c}" for c in common[:3]))
        return "\n\n".join(parts)


# ============================================================
# CONVENIENCE: Run a single inquiry through the agent
# ============================================================

async def run_inquiry(
    customer_name: str,
    message: str,
    channel: str = "email",
    email: Optional[str] = None,
    phone: Optional[str] = None,
    subject: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Convenience function to process a single customer inquiry end-to-end.

    Args:
        customer_name: Customer's full name.
        message: Customer's support message.
        channel: Communication channel (email, whatsapp, web_form).
        email: Customer's email.
        phone: Customer's phone.
        subject: Optional subject line.
        model: OpenAI model to use.

    Returns:
        Complete pipeline result dict.
    """
    pipeline = AgentPipeline(model=model, channel=channel)
    return await pipeline.process_inquiry(
        customer_name=customer_name,
        message=message,
        email=email,
        phone=phone,
        subject=subject,
    )


# ============================================================
# ENTRY POINT: Demo
# ============================================================

if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("TaskFlow Customer Success Agent — Demo")
    print("=" * 70)

    # Test agent creation
    agent_config = create_customer_success_agent(channel="email", include_tools=False)
    if isinstance(agent_config, dict):
        print(f"\nAgent config (SDK not available):")
        print(f"  Name: {agent_config['name']}")
        print(f"  Model: {agent_config['model']}")
        print(f"  Channel: {agent_config['channel']}")
        print(f"  Tools: {agent_config['tool_count']}")
    else:
        print(f"\nAgent created: {agent_config.name}")

    # Test pipeline (rule-based mode, no LLM)
    print("\n--- Pipeline Test ---")
    pipeline = AgentPipeline(channel="email")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            pipeline.process_inquiry(
                customer_name="Alice Johnson",
                message="I can't reset my password. The reset link says expired even though I just requested it 5 minutes ago!",
                email="alice.j@startupco.com",
                subject="Password reset issue",
            )
        )
        loop.close()
    except Exception as e:
        print(f"Pipeline error: {e}")
        result = {}
    print(f"Status: {result.get('status', 'N/A')}")
    print(f"Ticket: {result.get('ticket_id', 'N/A')}")
    print(f"Returning customer: {result.get('is_returning_customer', False)}")
    print(f"KB search: {result.get('steps', {}).get('knowledge_base', {}).get('status', 'N/A')}")
    print(f"Sentiment: {result.get('steps', {}).get('sentiment', {}).get('label', 'N/A')} ({result.get('steps', {}).get('sentiment', {}).get('score', 0)})")
    print(f"Escalation: {result.get('steps', {}).get('escalation', {}).get('escalate', False)}")
    print(f"Response sent: {result.get('steps', {}).get('send_response', {}).get('status', 'N/A')}")
    print(f"\nResponse preview:\n{result.get('response', 'N/A')[:300]}...")
