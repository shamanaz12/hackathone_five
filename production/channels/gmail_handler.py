"""
TaskFlow AI Support Agent — Gmail Channel Handler
CRM Digital FTE Factory Final Hackathon 5

Handles:
- Gmail Pub/Sub webhook processing
- Email parsing (sender, subject, body, attachments)
- Reply sending via Gmail API / SMTP
- Thread management
"""

from __future__ import annotations

import base64
import email
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message
from typing import Optional

from production.config.settings import get_settings
from production.utils.helpers import extract_email, sanitize_input

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# EMAIL PARSER
# ============================================================

class EmailParser:
    """Parse raw email content into structured data."""

    @staticmethod
    def decode_header_value(raw: str) -> str:
        """Decode RFC 2047 encoded header values."""
        if not raw:
            return ""
        parts = decode_header(raw)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded).strip()

    @staticmethod
    def extract_body(msg: Message) -> tuple[str, str]:
        """
        Extract plain text and HTML body from email message.

        Returns:
            Tuple of (plain_text_body, html_body)
        """
        plain_text = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain" and not plain_text:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    plain_text = payload.decode(charset, errors="replace") if payload else ""

                elif content_type == "text/html" and not html_body:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace") if payload else ""
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            if payload:
                body = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html_body = body
                else:
                    plain_text = body

        return plain_text.strip(), html_body.strip()

    @staticmethod
    def strip_signature(text: str) -> str:
        """Remove email signature blocks."""
        # Remove everything after -- signature separator
        sig_pattern = r"\n\s*--\s*\n.*$"
        text = re.sub(sig_pattern, "", text, flags=re.DOTALL)
        # Remove common signature patterns
        text = re.sub(r"\n\s*--\s*$", "", text)
        text = re.sub(r"\n\s*Sent from my .*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n\s*Get Outlook for .*", "", text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def strip_quoted_reply(text: str) -> str:
        """Remove quoted previous messages from reply emails."""
        patterns = [
            r"\n\s*On .*, .* wrote:.*$",
            r"\n\s*From:.*$",
            r"\n\s*>.*$",
            r"\n\s*-{3,} Original Message -{3,}.*$",
            r"\n\s*_{3,}.*$",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        return text.strip()

    @classmethod
    def parse_raw_email(cls, raw_email: str) -> dict:
        """
        Parse a raw email string (RFC 822 format) into structured data.

        Args:
            raw_email: Raw email content as string.

        Returns:
            Dictionary with sender, recipient, subject, body, html_body,
            date, message_id, in_reply_to, references, attachments.
        """
        msg = email.message_from_string(raw_email)

        # Decode headers
        from_header = cls.decode_header_value(msg.get("From", ""))
        to_header = cls.decode_header_value(msg.get("To", ""))
        subject = cls.decode_header_value(msg.get("Subject", "(No Subject)"))

        # Extract sender email
        sender_email = extract_email(from_header)

        # Extract body
        plain_text, html_body = cls.extract_body(msg)

        # Clean body text
        clean_body = cls.strip_signature(plain_text)
        clean_body = cls.strip_quoted_reply(clean_body)

        # Extract attachments info
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                disposition = part.get("Content-Disposition", "")
                if "attachment" in str(disposition).lower():
                    attachments.append({
                        "filename": part.get_filename("unknown"),
                        "content_type": part.get_content_type(),
                        "size": len(part.get_payload(decode=True) or b""),
                    })

        return {
            "from_name": from_header,
            "from_email": sender_email,
            "to": to_header,
            "subject": subject,
            "body": sanitize_input(clean_body),
            "html_body": html_body,
            "date": msg.get("Date", ""),
            "message_id": msg.get("Message-ID", ""),
            "in_reply_to": msg.get("In-Reply-To", ""),
            "references": msg.get("References", ""),
            "attachments": attachments,
            "is_reply": bool(msg.get("In-Reply-To")),
        }

    @classmethod
    def parse_gmail_api_message(cls, gmail_message: dict) -> dict:
        """
        Parse a Gmail API message resource into structured data.

        Args:
            gmail_message: Gmail API message object (from users.messages.get).

        Returns:
            Same structure as parse_raw_email.
        """
        headers = {h["name"]: h["value"] for h in gmail_message.get("payload", {}).get("headers", [])}

        from_header = headers.get("From", "")
        to_header = headers.get("To", "")
        subject = headers.get("Subject", "(No Subject)")
        sender_email = extract_email(from_header)

        # Extract body from parts
        plain_text = ""
        html_body = ""
        attachments = []

        def _extract_parts(payload_part):
            nonlocal plain_text, html_body, attachments
            mime_type = payload_part.get("mimeType", "")
            filename = payload_part.get("filename", "")
            body_data = payload_part.get("body", {}).get("data", "")

            if filename:
                attachments.append({
                    "filename": filename,
                    "content_type": mime_type,
                    "size": payload_part.get("body", {}).get("size", 0),
                })
            elif mime_type == "text/plain" and body_data and not plain_text:
                plain_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            elif mime_type == "text/html" and body_data and not html_body:
                html_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

            # Recurse into parts
            for part in payload_part.get("parts", []):
                _extract_parts(part)

        _extract_parts(gmail_message.get("payload", {}))

        clean_body = cls.strip_signature(plain_text)
        clean_body = cls.strip_quoted_reply(clean_body)

        return {
            "from_name": from_header,
            "from_email": sender_email,
            "to": to_header,
            "subject": subject,
            "body": sanitize_input(clean_body),
            "html_body": html_body,
            "date": headers.get("Date", ""),
            "message_id": headers.get("Message-ID", ""),
            "in_reply_to": headers.get("In-Reply-To", ""),
            "references": headers.get("References", ""),
            "attachments": attachments,
            "is_reply": bool(headers.get("In-Reply-To")),
            "gmail_thread_id": gmail_message.get("threadId", ""),
            "gmail_message_id": gmail_message.get("id", ""),
            "gmail_label_ids": gmail_message.get("labelIds", []),
        }


# ============================================================
# GMAIL HANDLER
# ============================================================

class GmailHandler:
    """
    Process Gmail webhooks and send replies.

    Workflow:
    1. Receive Pub/Sub notification
    2. Fetch email via Gmail API
    3. Parse email content
    4. Create ticket / run agent pipeline
    5. Send AI response via Gmail API
    """

    def __init__(self, gmail_client=None):
        """
        Initialize Gmail handler.

        Args:
            gmail_client: Authenticated Gmail API client (googleapiclient.discovery.build).
                         If None, uses service account authentication.
        """
        self.gmail_client = gmail_client
        self.support_email = settings.support_email
        self.parser = EmailParser()

    def _get_client(self):
        """Get or initialize Gmail API client. Returns None in mock/dev mode."""
        if self.gmail_client:
            return self.gmail_client

        # Try to initialize from service account if configured
        if settings.gmail_service_account_file and settings.gmail_project_id:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                credentials = service_account.Credentials.from_service_account_file(
                    settings.gmail_service_account_file,
                    scopes=["https://www.googleapis.com/auth/gmail.modify"],
                )
                self.gmail_client = build("gmail", "v1", credentials=credentials)
                logger.info("Gmail API client initialized from service account")
                return self.gmail_client
            except Exception as exc:
                logger.warning("Failed to init Gmail API client: %s — using mock mode", exc)

        logger.info("Gmail API not configured — running in mock mode")
        return None

    # ── Webhook Processing ──

    def process_webhook(self, pubsub_message: dict) -> dict:
        """
        Process a Gmail Pub/Sub webhook notification.

        Args:
            pubsub_message: Pub/Sub message dict with 'data' (base64) and 'attributes'.

        Returns:
            Processing result dict with status, ticket_id, and email data.
        """
        try:
            # Decode Pub/Sub message
            data = pubsub_message.get("data", "")
            decoded_data = base64.b64decode(data).decode("utf-8")
            logger.info("Gmail Pub/Sub message decoded: %s", decoded_data[:200])

            # Extract history ID and email address
            attributes = pubsub_message.get("attributes", {})
            email_address = attributes.get("emailAddress", "")
            history_id = attributes.get("historyId", "")

            logger.info(
                "Gmail notification for %s (historyId: %s)",
                email_address, history_id,
            )

            # Try to fetch via Gmail API first
            client = self._get_client()
            if client:
                gmail_message = self._fetch_latest_message()
                if not gmail_message:
                    return {"status": "no_message", "message": "No new messages found"}
                parsed = self.parser.parse_gmail_api_message(gmail_message)
            else:
                # Mock mode: decode data as raw RFC 822 email
                parsed = self.parser.parse_raw_email(decoded_data)

            logger.info(
                "Email parsed — from: %s, subject: %s, body_len: %d",
                parsed["from_email"], parsed["subject"], len(parsed["body"]),
            )

            # Check if this is from our support address (avoid loops)
            if parsed["from_email"] == self.support_email:
                return {"status": "skipped", "message": "Email from support address — skipping"}

            return {
                "status": "processed",
                "email": parsed,
                "ticket_id": None,
                "history_id": history_id,
            }

        except Exception as exc:
            logger.error("Gmail webhook processing failed: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    def _fetch_latest_message(self) -> Optional[dict]:
        """Fetch the latest unread message from the support inbox."""
        try:
            client = self._get_client()
            # TODO: List messages with query
            # response = client.users().messages().list(
            #     userId="me",
            #     q=f"is:unread to:{self.support_email}",
            #     maxResults=1,
            # ).execute()
            # messages = response.get("messages", [])
            # if not messages:
            #     return None
            # return client.users().messages().get(
            #     userId="me",
            #     id=messages[0]["id"],
            #     format="full",
            # ).execute()
            return None  # Placeholder

        except Exception as exc:
            logger.error("Failed to fetch Gmail message: %s", exc, exc_info=True)
            return None

    # ── Send Reply ──

    def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        """
        Send an email reply via Gmail API.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            body: Plain text body.
            html_body: Optional HTML body.
            in_reply_to: Message-ID of the email being replied to.
            references: References header for threading.
            thread_id: Gmail thread ID for threading.

        Returns:
            Dict with status and sent message info.
        """
        try:
            # Build MIME message
            message = self._build_mime_message(
                to_email=to_email,
                from_email=self.support_email,
                subject=subject,
                body=body,
                html_body=html_body,
                in_reply_to=in_reply_to,
                references=references,
            )

            # Encode for Gmail API
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send via Gmail API
            client = self._get_client()
            if client:
                send_kwargs = {
                    "userId": "me",
                    "body": {"raw": raw},
                }
                if thread_id:
                    send_kwargs["body"]["threadId"] = thread_id

                sent = client.users().messages().send(**send_kwargs).execute()
                logger.info("Reply sent to %s — subject: %s — gmail_id: %s", to_email, subject, sent.get("id", ""))
            else:
                logger.info(
                    "[MOCK] Reply would be sent to %s — subject: %s — body_len: %d",
                    to_email, subject, len(body),
                )

            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error("Failed to send Gmail reply: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    def _build_mime_message(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Message:
        """Build a MIME email message."""
        msg = Message()
        msg["To"] = to_email
        msg["From"] = from_email
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        # Threading headers
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        # Generate Message-ID
        import uuid
        msg["Message-ID"] = f"<{uuid.uuid4()}@techcorp.com>"

        # Body
        if html_body:
            # Multipart alternative (plain text + HTML)
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body, "plain", "utf-8"))
            alt.attach(MIMEText(html_body, "html", "utf-8"))
            msg.set_payload(None)
            msg.attach(alt)
        else:
            msg.set_payload(body, charset="utf-8")

        return msg

    # ── Label Management ──

    def add_label(self, message_id: str, label: str) -> dict:
        """Add a label to a Gmail message."""
        try:
            client = self._get_client()
            # TODO: client.users().messages().modify(
            #     userId="me",
            #     id=message_id,
            #     body={"addLabelIds": [label]},
            # ).execute()
            return {"status": "ok", "message_id": message_id, "label": label}
        except Exception as exc:
            logger.error("Failed to add label: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    def mark_as_read(self, message_id: str) -> dict:
        """Mark a Gmail message as read (remove UNREAD label)."""
        return self.add_label(message_id, "-UNREAD")

    def mark_as_replied(self, message_id: str) -> dict:
        """Mark a Gmail message as replied (add custom label)."""
        return self.add_label(message_id, "Label_replied")

    # ── Pub/Sub Subscription Setup ──

    @staticmethod
    def create_watch_request(topic_name: str, label_ids: Optional[list] = None) -> dict:
        """
        Create a Gmail watch request for Pub/Sub notifications.

        Args:
            topic_name: Full Pub/Sub topic name (projects/PROJECT/topics/TOPIC).
            label_ids: Optional list of label IDs to watch (e.g., ["UNREAD", "INBOX"]).

        Returns:
            Watch request body for Gmail API.
        """
        return {
            "labelIds": label_ids or ["UNREAD", "INBOX"],
            "topicName": topic_name,
        }

    @staticmethod
    def create_push_subscription(topic_name: str, subscription_name: str, endpoint: str) -> dict:
        """
        Create a Pub/Sub push subscription.

        Args:
            topic_name: Full topic name.
            subscription_name: Full subscription name.
            endpoint: HTTPS endpoint for push notifications.

        Returns:
            Subscription config dict.
        """
        return {
            "topic": topic_name,
            "name": subscription_name,
            "pushConfig": {
                "pushEndpoint": endpoint,
                "attributes": {"x-goog-version": "v1"},
            },
            "ackDeadlineSeconds": 60,
        }
