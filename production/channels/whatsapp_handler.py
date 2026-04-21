"""
TaskFlow AI Support Agent — WhatsApp Channel Handler
CRM Digital FTE Factory Final Hackathon 5

Handles:
- WhatsApp Cloud API webhook processing
- Message parsing (text, image, document, audio, video)
- Reply sending via WhatsApp Cloud API
- Template messages for structured responses
- Media upload/download
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from production.config.settings import get_settings
from production.utils.helpers import sanitize_input

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# WHATSAPP MESSAGE TYPES
# ============================================================

class WhatsAppMessageType:
    """Constants for WhatsApp message types."""
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contacts"
    REACTION = "reaction"
    BUTTON = "button"
    LIST = "list"
    INTERACTIVE = "interactive"
    UNKNOWN = "unknown"


# ============================================================
# WHATSAPP HANDLER
# ============================================================

class WhatsAppHandler:
    """
    Process WhatsApp webhooks and send replies via Cloud API.

    Workflow:
    1. Receive webhook POST from Meta
    2. Extract sender phone, message type, content
    3. Resolve customer identity by phone
    4. Run through agent pipeline
    5. Send response via WhatsApp Cloud API
    """

    BASE_URL = "https://graph.facebook.com/{api_version}"

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize WhatsApp handler.

        Args:
            phone_number_id: WhatsApp Business API phone number ID.
            access_token: WhatsApp Cloud API access token.
            api_version: API version (e.g., "v18.0").
            http_client: Async HTTP client for API calls.
        """
        self.phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self.access_token = access_token or settings.whatsapp_access_token
        self.api_version = api_version or settings.whatsapp_api_version
        self.http_client = http_client
        self._base_url = self.BASE_URL.format(api_version=self.api_version)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            return self.http_client
            
        if not self.access_token:
            logger.warning("WhatsApp access token not set — API calls will fail")
            # Return a client without auth header or handle it differently
            self.http_client = httpx.AsyncClient(timeout=30.0)
            return self.http_client

        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )
        return self.http_client

    # ── Webhook Verification ──

    @staticmethod
    def verify_webhook_token(
        hub_mode: str,
        hub_verify_token: str,
        hub_challenge: str,
        expected_token: Optional[str] = None,
    ) -> Optional[str]:
        """
        Verify WhatsApp webhook registration request.

        Meta sends a GET request to verify the webhook URL before
        forwarding messages. We must echo back the challenge string.

        Args:
            hub_mode: Should be "subscribe".
            hub_verify_token: Token we configured.
            hub_challenge: Challenge string to echo back.
            expected_token: Expected verify token (defaults to settings).

        Returns:
            Challenge string if verification succeeds, None otherwise.
        """
        token = expected_token or settings.whatsapp_verify_token
        if hub_mode == "subscribe" and hub_verify_token == token:
            logger.info("WhatsApp webhook verification successful.")
            return hub_challenge
        logger.warning(
            "WhatsApp webhook verification failed — mode: %s, token match: %s",
            hub_mode, hub_verify_token == token,
        )
        return None

    # ── Webhook Processing ──

    def process_webhook(self, payload: dict) -> list[dict]:
        """
        Process a WhatsApp webhook payload from Meta.

        Args:
            payload: Webhook POST body from Meta.

        Returns:
            List of processed message dicts with sender, type, content.
        """
        results = []

        try:
            entries = payload.get("entry", [])
            logger.info("WhatsApp webhook received — entries: %d", len(entries))

            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])

                    # Build contact lookup
                    contact_map = {}
                    for contact in contacts:
                        wa_id = contact.get("wa_id", "")
                        profile = contact.get("profile", {})
                        contact_map[wa_id] = profile.get("name", "Unknown")

                    for msg in messages:
                        sender_wa_id = msg.get("from", "")
                        msg_type = msg.get("type", WhatsAppMessageType.UNKNOWN)
                        timestamp = msg.get("timestamp", "")
                        msg_id = msg.get("id", "")

                        # Extract content based on message type
                        content = self._extract_message_content(msg, msg_type)
                        sender_name = contact_map.get(sender_wa_id, "Unknown")

                        logger.info(
                            "WhatsApp %s from %s (%s): %s",
                            msg_type, sender_wa_id, sender_name, content[:100],
                        )

                        processed = {
                            "sender_phone": sender_wa_id,
                            "sender_name": sender_name,
                            "message_type": msg_type,
                            "content": sanitize_input(content),
                            "timestamp": timestamp,
                            "message_id": msg_id,
                            "channel": "whatsapp",
                        }

                        # TODO: Run through agent pipeline
                        # response_text = agent_pipeline.process_whatsapp(processed)
                        # await self.send_text_reply(sender_wa_id, response_text)

                        results.append(processed)

            return results

        except Exception as exc:
            logger.error("WhatsApp webhook processing failed: %s", exc, exc_info=True)
            return [{"status": "error", "message": str(exc)}]

    async def handle_incoming_messages(self, payload: dict) -> list[dict]:
        """
        Process a WhatsApp webhook and run each message through the AI agent pipeline.
        """
        from production.agent.customer_success_agent import AgentPipeline
        
        messages = self.process_webhook(payload)
        pipeline = AgentPipeline(channel="whatsapp")
        
        results = []
        for msg in messages:
            if msg.get("status") == "error":
                results.append(msg)
                continue
                
            agent_result = await pipeline.process_inquiry(
                customer_name=msg.get("sender_name", "Valued Customer"),
                message=msg.get("content", ""),
                phone=msg.get("sender_phone"),
            )
            
            ai_response = agent_result.get("response", "Thank you for your message.")
            
            # Send reply
            await self.send_text_reply(
                recipient_phone=msg.get("sender_phone"),
                text=ai_response
            )
            
            msg["ticket_id"] = agent_result.get("ticket_id")
            msg["ai_response"] = ai_response
            msg["status"] = "completed"
            results.append(msg)
            
        return results

    @staticmethod
    def _extract_message_content(msg: dict, msg_type: str) -> str:
        """Extract text content from a WhatsApp message based on its type."""
        if msg_type == WhatsAppMessageType.TEXT:
            return msg.get("text", {}).get("body", "")

        elif msg_type == WhatsAppMessageType.IMAGE:
            image = msg.get("image", {})
            caption = image.get("caption", "")
            mime = image.get("mime_type", "image")
            return f"[Image: {mime}]" + (f" {caption}" if caption else "")

        elif msg_type == WhatsAppMessageType.DOCUMENT:
            doc = msg.get("document", {})
            filename = doc.get("filename", "document")
            caption = doc.get("caption", "")
            return f"[Document: {filename}]" + (f" {caption}" if caption else "")

        elif msg_type == WhatsAppMessageType.AUDIO:
            audio = msg.get("audio", {})
            mime = audio.get("mime_type", "audio")
            voice = audio.get("voice", False)
            return f"[{'Voice' if voice else 'Audio'} message: {mime}]"

        elif msg_type == WhatsAppMessageType.VIDEO:
            video = msg.get("video", {})
            caption = video.get("caption", "")
            mime = video.get("mime_type", "video")
            return f"[Video: {mime}]" + (f" {caption}" if caption else "")

        elif msg_type == WhatsAppMessageType.LOCATION:
            loc = msg.get("location", {})
            return f"[Location: {loc.get('name', '')}, {loc.get('address', '')}]"

        elif msg_type == WhatsAppMessageType.CONTACT:
            contacts = msg.get("contacts", [])
            names = [c.get("name", {}).get("formatted_name", "") for c in contacts]
            return f"[Contact: {', '.join(names)}]"

        elif msg_type == WhatsAppMessageType.REACTION:
            reaction = msg.get("reaction", {})
            return f"[Reaction: {reaction.get('emoji', '?')} to {reaction.get('message_id', '')}]"

        elif msg_type in (WhatsAppMessageType.BUTTON, WhatsAppMessageType.LIST, WhatsAppMessageType.INTERACTIVE):
            interactive = msg.get("interactive", {})
            return f"[Interactive: {interactive}]"

        return f"[Unsupported message type: {msg_type}]"

    # ── Send Replies ──

    async def send_text_reply(
        self,
        recipient_phone: str,
        text: str,
        preview_url: bool = False,
    ) -> dict:
        """
        Send a text reply via WhatsApp Cloud API.

        Args:
            recipient_phone: Customer's WhatsApp number (with country code).
            text: Message text (max 4096 characters).
            preview_url: Whether to generate link previews.

        Returns:
            API response dict with status and message ID.
        """
        # Truncate if too long (WhatsApp limit is 4096 chars)
        if len(text) > 4000:
            text = text[:4000] + "\n\n[Message truncated — full details sent via email]"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "body": text,
                "preview_url": preview_url,
            },
        }

        return await self._send_message(payload, "text")

    async def send_template_reply(
        self,
        recipient_phone: str,
        template_name: str,
        language_code: str = "en",
        components: Optional[list[dict]] = None,
    ) -> dict:
        """
        Send a template message reply.

        Templates are pre-approved message formats used for
        notifications, confirmations, and structured responses.

        Args:
            recipient_phone: Customer's WhatsApp number.
            template_name: Approved template name.
            language_code: Template language code (e.g., "en", "es").
            components: Template components (header, body variables, buttons).

        Returns:
            API response dict.
        """
        body_components = []
        if components:
            body_components = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": body_components,
            },
        }

        return await self._send_message(payload, "template")

    async def send_interactive_reply(
        self,
        recipient_phone: str,
        body_text: str,
        footer_text: Optional[str] = None,
        buttons: Optional[list[dict]] = None,
    ) -> dict:
        """
        Send an interactive message with quick reply buttons.

        Max 3 buttons, each with max 20 character title.

        Args:
            recipient_phone: Customer's WhatsApp number.
            body_text: Main message text.
            footer_text: Optional footer text (small, gray).
            buttons: List of button dicts: [{"id": "1", "title": "Yes"}].

        Returns:
            API response dict.
        """
        if not buttons:
            buttons = [
                {"id": "1", "title": "Yes"},
                {"id": "2", "title": "No"},
            ]

        action_buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
            for b in buttons[:3]
        ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": action_buttons},
            },
        }

        if footer_text:
            payload["interactive"]["footer"] = {"text": footer_text[:60]}

        return await self._send_message(payload, "interactive")

    async def send_list_reply(
        self,
        recipient_phone: str,
        header_text: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        footer_text: Optional[str] = None,
    ) -> dict:
        """
        Send a list message with selectable sections.

        Used for menus, FAQs, or multi-option responses.

        Args:
            recipient_phone: Customer's WhatsApp number.
            header_text: Header text (max 60 chars).
            body_text: Main message body.
            button_text: Button label (e.g., "View Options").
            sections: List of section dicts with title and rows.
            footer_text: Optional footer text.

        Returns:
            API response dict.
        """
        formatted_sections = []
        for section in sections:
            formatted_rows = [
                {"id": row["id"], "title": row["title"][:24], "description": row.get("description", "")[:72]}
                for row in section.get("rows", [])
            ]
            formatted_sections.append({
                "title": section.get("title", "")[:24],
                "rows": formatted_rows,
            })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header_text[:60]},
                "body": {"text": body_text},
                "action": {
                    "button": button_text[:20],
                    "sections": formatted_sections,
                },
            },
        }

        if footer_text:
            payload["interactive"]["footer"] = {"text": footer_text[:60]}

        return await self._send_message(payload, "list")

    async def send_media_reply(
        self,
        recipient_phone: str,
        media_type: str,
        media_url: Optional[str] = None,
        media_id: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> dict:
        """
        Send a media reply (image, document, video, audio).

        Args:
            recipient_phone: Customer's WhatsApp number.
            media_type: One of: image, document, video, audio, sticker.
            media_url: Public URL of the media (must be HTTPS).
            media_id: Previously uploaded media ID (alternative to URL).
            caption: Optional caption for image/document/video.

        Returns:
            API response dict.
        """
        if not media_url and not media_id:
            raise ValueError("Either media_url or media_id must be provided")

        media_payload = {
            "link": media_url,
            "id": media_id,
        }
        if caption:
            media_payload["caption"] = caption[:1024]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": media_type,
            media_type: media_payload,
        }

        return await self._send_message(payload, media_type)

    async def send_reaction(
        self,
        recipient_phone: str,
        message_id: str,
        emoji: str,
    ) -> dict:
        """
        React to a message with an emoji.

        Args:
            recipient_phone: Customer's WhatsApp number.
            message_id: ID of the message to react to.
            emoji: Emoji character (e.g., "👍", "❤️").

        Returns:
            API response dict.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "reaction",
            "reaction": {
                "message_id": message_id,
                "emoji": emoji,
            },
        }

        return await self._send_message(payload, "reaction")

    async def mark_message_read(
        self,
        message_id: str,
    ) -> dict:
        """
        Mark a WhatsApp message as read (blue double check).

        Args:
            message_id: ID of the message to mark as read.

        Returns:
            API response dict.
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            client = await self._get_client()
            url = f"{self._base_url}/{self.phone_number_id}/messages"
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Message %s marked as read", message_id)
            return {"status": "ok", "message_id": message_id}
        except Exception as exc:
            logger.error("Failed to mark message as read: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    # ── Internal: Send Message ──

    async def _send_message(self, payload: dict, msg_type: str) -> dict:
        """
        Send a message via WhatsApp Cloud API.

        Args:
            payload: Message payload dict.
            msg_type: Message type for logging.

        Returns:
            API response dict with status and message ID.
        """
        try:
            client = await self._get_client()
            url = f"{self._base_url}/{self.phone_number_id}/messages"

            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            message_id = ""
            if "messages" in data:
                message_id = data["messages"][0].get("id", "")

            logger.info(
                "WhatsApp %s sent to %s — message_id: %s",
                msg_type, payload.get("to", ""), message_id,
            )

            return {
                "status": "sent",
                "message_id": message_id,
                "recipient": payload.get("to", ""),
                "type": msg_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_response": data,
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API HTTP error %d: %s",
                exc.response.status_code, exc.response.text,
            )
            return {
                "status": "error",
                "code": exc.response.status_code,
                "message": exc.response.text,
            }

        except Exception as exc:
            logger.error("WhatsApp send failed: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    # ── Media Upload ──

    async def upload_media(self, file_path: str, file_type: str = "image/png") -> dict:
        """
        Upload media to WhatsApp servers for later use in messages.

        Args:
            file_path: Local path to the file.
            file_type: MIME type of the file.

        Returns:
            Dict with media_id for use in send_media_reply.
        """
        try:
            client = await self._get_client()
            url = f"{self._base_url}/{self.phone_number_id}/media"

            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.split("/")[-1], f, file_type),
                }
                data = {"messaging_product": "whatsapp", "type": file_type}
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                result = response.json()

            media_id = result.get("id", "")
            logger.info("Media uploaded — id: %s", media_id)

            return {
                "status": "uploaded",
                "media_id": media_id,
                "file_path": file_path,
            }

        except Exception as exc:
            logger.error("Media upload failed: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Download media from WhatsApp servers.

        Args:
            media_id: Media ID from a received message.

        Returns:
            Raw file bytes or None on failure.
        """
        try:
            client = await self._get_client()

            # Step 1: Get media URL
            url = f"{self._base_url}/{media_id}"
            response = await client.get(url)
            response.raise_for_status()
            media_info = response.json()
            media_url = media_info.get("url", "")

            # Step 2: Download the file (auth required)
            download_response = await client.get(media_url)
            download_response.raise_for_status()

            logger.info("Media downloaded — id: %s, size: %d bytes", media_id, len(download_response.content))
            return download_response.content

        except Exception as exc:
            logger.error("Media download failed: %s", exc, exc_info=True)
            return None

    # ── Cleanup ──

    async def close(self):
        """Close the HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
            logger.info("WhatsApp HTTP client closed")
