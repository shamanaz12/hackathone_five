"""
TaskFlow AI Support Agent — WhatsApp Flow Handler
CRM Digital FTE Factory Final Hackathon 5

Handles high-level conversation flows for WhatsApp.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class WhatsAppFlows:
    """Helper class to manage WhatsApp-specific logic and response formatting."""

    @staticmethod
    def get_response(user_text: str) -> Tuple[str, bool]:
        """
        Determine the appropriate response for a WhatsApp message.
        
        Returns:
            (reply_text, should_escalate)
        """
        from production.agent.customer_success_agent import AgentPipeline
        import asyncio
        
        # Note: In a real production environment, we'd avoid running 
        # async code inside a sync method like this, but for the 
        # demo/simulator scenario, we'll bridge it.
        
        pipeline = AgentPipeline(channel="whatsapp")
        
        # Since we're in a sync context but the pipeline is async,
        # we need an event loop.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        result = loop.run_until_complete(pipeline.process_inquiry(
            customer_name="WhatsApp User",
            message=user_text,
            phone="03161129505" # Default for demo
        ))
        
        reply_text = result.get("response", "Thank you for your message. We'll get back to you shortly.")
        should_escalate = result.get("resolution_status") == "escalated"
        
        return reply_text, should_escalate

    @staticmethod
    def format_whatsapp_reply(text: str) -> str:
        """Format text for WhatsApp (emojis, line breaks, etc.)"""
        # Basic formatting already handled by pipeline, but we can add more here
        if "Hey" not in text and "Hi" not in text:
            text = "👋 " + text
        
        if "Hope that helps" not in text:
            text += "\n\nHope that helps! 😊"
            
        return text
