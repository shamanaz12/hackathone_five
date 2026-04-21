"""
TaskFlow AI Support Agent — Unified Message Processor Worker
CRM Digital FTE Factory Final Hackathon 5

Consumes messages from Kafka topics (email, whatsapp, web_form),
runs them through the Customer Success Agent pipeline, and publishes
results to response/error topics.

Topics:
  - taskflow.incoming.email      — Gmail webhook events
  - taskflow.incoming.whatsapp   — WhatsApp webhook events
  - taskflow.incoming.web_form   — Web form submissions
  - taskflow.outgoing.responses  — AI-generated responses ready for delivery
  - taskflow.outgoing.escalations — Tickets requiring human handoff
  - taskflow.errors.dead_letter  — Unprocessable messages
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from production.agent.customer_success_agent import AgentPipeline, create_customer_success_agent
from production.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# KAFKA TOPIC CONSTANTS
# ============================================================

class KafkaTopics:
    """Kafka topic names for the TaskFlow message pipeline."""
    INCOMING_EMAIL = "taskflow.incoming.email"
    INCOMING_WHATSAPP = "taskflow.incoming.whatsapp"
    INCOMING_WEB_FORM = "taskflow.incoming.web_form"
    OUTGOING_RESPONSES = "taskflow.outgoing.responses"
    OUTGOING_ESCALATIONS = "taskflow.outgoing.escalations"
    ERRORS_DEAD_LETTER = "taskflow.errors.dead_letter"

    ALL_INCOMING = [INCOMING_EMAIL, INCOMING_WHATSAPP, INCOMING_WEB_FORM]
    ALL_OUTGOING = [OUTGOING_RESPONSES, OUTGOING_ESCALATIONS]


# ============================================================
# MESSAGE TYPES
# ============================================================

class MessageChannel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class UnifiedMessage:
    """Normalized message consumed from any Kafka topic."""
    message_id: str
    channel: str
    raw_payload: dict
    customer_name: str = ""
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    subject: Optional[str] = None
    content: str = ""
    metadata: dict = field(default_factory=dict)
    received_at: str = ""
    kafka_offset: int = 0
    kafka_partition: int = 0
    kafka_topic: str = ""
    retry_count: int = 0
    max_retries: int = 3
    status: str = ProcessingStatus.PENDING.value
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.received_at:
            self.received_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class ProcessingResult:
    """Result of processing a unified message."""
    message_id: str
    ticket_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: str = ProcessingStatus.COMPLETED.value
    response_text: str = ""
    escalation_needed: bool = False
    escalation_team: str = ""
    escalation_sla: str = ""
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    pipeline_steps: dict = field(default_factory=dict)
    output_topic: str = ""
    output_payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ============================================================
# METRICS COLLECTOR
# ============================================================

class ProcessingMetrics:
    """Collects and reports processing metrics."""

    def __init__(self):
        self.total_processed = 0
        self.total_succeeded = 0
        self.total_failed = 0
        self.total_retried = 0
        self.total_dead_lettered = 0
        self.total_escalated = 0
        self.processing_times: list[float] = []
        self.errors_by_type: dict[str, int] = {}
        self.messages_by_channel: dict[str, int] = {}
        self.messages_by_topic: dict[str, int] = {}
        self.started_at = datetime.now(timezone.utc)

    def record_success(self, channel: str, topic: str, processing_time_ms: float):
        self.total_processed += 1
        self.total_succeeded += 1
        self.processing_times.append(processing_time_ms)
        self.messages_by_channel[channel] = self.messages_by_channel.get(channel, 0) + 1
        self.messages_by_topic[topic] = self.messages_by_topic.get(topic, 0) + 1

    def record_failure(self, channel: str, error_type: str):
        self.total_processed += 1
        self.total_failed += 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.messages_by_channel[channel] = self.messages_by_channel.get(channel, 0) + 1

    def record_retry(self):
        self.total_retried += 1

    def record_dead_letter(self):
        self.total_dead_lettered += 1

    def record_escalation(self):
        self.total_escalated += 1

    def get_summary(self) -> dict:
        avg_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0
        )
        p95_time = (
            sorted(self.processing_times)[int(len(self.processing_times) * 0.95)]
            if self.processing_times else 0
        )
        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()

        return {
            "uptime_seconds": round(uptime, 1),
            "total_processed": self.total_processed,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_retried": self.total_retried,
            "total_dead_lettered": self.total_dead_lettered,
            "total_escalated": self.total_escalated,
            "success_rate": round(
                self.total_succeeded / max(self.total_processed, 1) * 100, 1
            ),
            "avg_processing_time_ms": round(avg_time, 1),
            "p95_processing_time_ms": round(p95_time, 1),
            "errors_by_type": self.errors_by_type,
            "messages_by_channel": self.messages_by_channel,
            "messages_by_topic": self.messages_by_topic,
        }


# ============================================================
# KAFKA PRODUCER (async wrapper)
# ============================================================

class KafkaProducerWrapper:
    """Async Kafka producer for publishing results."""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer = None
        self._initialized = False

    async def initialize(self):
        """Initialize the Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                acks="all",
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            await self._producer.start()
            self._initialized = True
            logger.info("Kafka producer initialized — brokers: %s", self.bootstrap_servers)
        except ImportError:
            logger.warning("aiokafka not installed — producer in mock mode")
            self._initialized = True
        except Exception as exc:
            logger.error("Failed to initialize Kafka producer: %s", exc, exc_info=True)
            raise

    async def send(self, topic: str, payload: dict, key: Optional[str] = None):
        """Send a message to a Kafka topic."""
        if not self._initialized:
            await self.initialize()

        try:
            if self._producer:
                await self._producer.send_and_wait(
                    topic=topic,
                    value=payload,
                    key=key.encode("utf-8") if key else None,
                )
                logger.debug("Published to %s — key: %s", topic, key)
            else:
                # Mock mode — log instead
                logger.info(
                    "[MOCK] Would publish to %s — key: %s — payload: %s",
                    topic, key, str(payload)[:200],
                )
        except Exception as exc:
            logger.error("Failed to publish to %s: %s", topic, exc, exc_info=True)
            raise

    async def close(self):
        """Close the Kafka producer."""
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")


# ============================================================
# KAFKA CONSUMER (async wrapper)
# ============================================================

class KafkaConsumerWrapper:
    """Async Kafka consumer for reading messages from topics."""

    def __init__(
        self,
        topics: list[str],
        group_id: str = "taskflow-agent-workers",
        bootstrap_servers: Optional[str] = None,
    ):
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._consumer = None
        self._initialized = False

    async def initialize(self):
        """Initialize the Kafka consumer."""
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                max_poll_records=10,
                max_poll_interval_ms=300000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )
            await self._consumer.start()
            self._initialized = True
            logger.info(
                "Kafka consumer initialized — topics: %s, group: %s",
                self.topics, self.group_id,
            )
        except ImportError:
            logger.warning("aiokafka not installed — consumer in mock mode")
            self._initialized = True
        except Exception as exc:
            logger.error("Failed to initialize Kafka consumer: %s", exc, exc_info=True)
            raise

    async def poll(self, timeout_ms: int = 5000) -> list[dict]:
        """
        Poll for new messages.

        Returns:
            List of message dicts with topic, partition, offset, key, value.
        """
        if not self._initialized:
            await self.initialize()

        messages = []
        try:
            if self._consumer:
                records = await self._consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=10,
                )
                for tp, batch in records.items():
                    for record in batch:
                        value = record.value
                        if isinstance(value, bytes):
                            value = json.loads(value.decode("utf-8"))
                        messages.append({
                            "topic": tp.topic,
                            "partition": tp.partition,
                            "offset": record.offset,
                            "key": record.key.decode("utf-8") if record.key else None,
                            "timestamp": record.timestamp,
                            "value": value,
                        })
            else:
                # Mock mode — return empty
                pass
        except Exception as exc:
            logger.error("Kafka poll failed: %s", exc, exc_info=True)

        return messages

    async def close(self):
        """Close the Kafka consumer."""
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")


# ============================================================
# UNIFIED MESSAGE PARSER
# ============================================================

class MessageParser:
    """Parse raw Kafka message payloads into UnifiedMessage objects."""

    @staticmethod
    def parse_email(payload: dict, kafka_meta: dict) -> UnifiedMessage:
        """Parse an email channel message from Gmail webhook."""
        email_data = payload.get("email", payload)
        return UnifiedMessage(
            message_id=payload.get("message_id", f"email-{time.time()}"),
            channel=MessageChannel.EMAIL.value,
            raw_payload=payload,
            customer_name=email_data.get("from_name", ""),
            customer_email=email_data.get("from_email"),
            subject=email_data.get("subject", ""),
            content=email_data.get("body", ""),
            metadata={
                "message_id_header": email_data.get("message_id"),
                "in_reply_to": email_data.get("in_reply_to"),
                "thread_id": email_data.get("gmail_thread_id"),
                "attachments": email_data.get("attachments", []),
            },
            kafka_offset=kafka_meta.get("offset", 0),
            kafka_partition=kafka_meta.get("partition", 0),
            kafka_topic=kafka_meta.get("topic", ""),
        )

    @staticmethod
    def parse_whatsapp(payload: dict, kafka_meta: dict) -> UnifiedMessage:
        """Parse a WhatsApp channel message from webhook."""
        # Handle nested webhook structure
        if "entry" in payload:
            # Full webhook — extract first message
            entry = payload.get("entry", [{}])[0]
            change = entry.get("changes", [{}])[0]
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            if not messages:
                raise ValueError("No messages in WhatsApp webhook payload")
            msg = messages[0]
            contact = contacts[0] if contacts else {}
            sender_phone = msg.get("from", "")
            sender_name = contact.get("profile", {}).get("name", "")
            msg_type = msg.get("type", "text")
            content = ""
            if msg_type == "text":
                content = msg.get("text", {}).get("body", "")
            else:
                content = f"[{msg_type} message received]"
        else:
            # Already parsed message
            sender_phone = payload.get("sender_phone", "")
            sender_name = payload.get("sender_name", "")
            content = payload.get("content", "")
            msg_type = payload.get("message_type", "text")

        return UnifiedMessage(
            message_id=payload.get("message_id", f"wa-{time.time()}"),
            channel=MessageChannel.WHATSAPP.value,
            raw_payload=payload,
            customer_name=sender_name,
            customer_phone=sender_phone,
            content=content,
            metadata={
                "message_type": msg_type,
                "whatsapp_id": payload.get("message_id"),
            },
            kafka_offset=kafka_meta.get("offset", 0),
            kafka_partition=kafka_meta.get("partition", 0),
            kafka_topic=kafka_meta.get("topic", ""),
        )

    @staticmethod
    def parse_web_form(payload: dict, kafka_meta: dict) -> UnifiedMessage:
        """Parse a web form submission message."""
        return UnifiedMessage(
            message_id=payload.get("ticket_id", f"wf-{time.time()}"),
            channel=MessageChannel.WEB_FORM.value,
            raw_payload=payload,
            customer_name=payload.get("customer_name", ""),
            customer_email=payload.get("email"),
            subject=payload.get("subject", ""),
            content=payload.get("message", ""),
            metadata={
                "category": payload.get("category"),
                "priority": payload.get("priority", "P3"),
                "form_url": payload.get("form_url", "/support"),
            },
            kafka_offset=kafka_meta.get("offset", 0),
            kafka_partition=kafka_meta.get("partition", 0),
            kafka_topic=kafka_meta.get("topic", ""),
        )

    @classmethod
    def parse(cls, payload: dict, kafka_meta: dict) -> UnifiedMessage:
        """
        Auto-detect channel and parse a raw Kafka message.

        Args:
            payload: The message value (dict).
            kafka_meta: Dict with topic, partition, offset, key.

        Returns:
            UnifiedMessage instance.

        Raises:
            ValueError: If channel cannot be determined.
        """
        topic = kafka_meta.get("topic", "")

        # Detect channel from topic
        if KafkaTopics.INCOMING_EMAIL in topic:
            return cls.parse_email(payload, kafka_meta)
        elif KafkaTopics.INCOMING_WHATSAPP in topic:
            return cls.parse_whatsapp(payload, kafka_meta)
        elif KafkaTopics.INCOMING_WEB_FORM in topic:
            return cls.parse_web_form(payload, kafka_meta)

        # Fallback: detect from payload
        if "entry" in payload or "sender_phone" in payload:
            return cls.parse_whatsapp(payload, kafka_meta)
        elif "customer_name" in payload and "message" in payload:
            return cls.parse_web_form(payload, kafka_meta)
        elif "from_email" in payload or "from_name" in payload:
            return cls.parse_email(payload, kafka_meta)

        raise ValueError(
            f"Cannot determine channel from topic '{topic}' or payload keys: {list(payload.keys())}"
        )


# ============================================================
# UNIFIED MESSAGE PROCESSOR
# ============================================================

class UnifiedMessageProcessor:
    """
    Main worker that consumes from Kafka, runs the agent pipeline,
    and publishes results to output topics.

    Lifecycle:
    1. Initialize Kafka consumer + producer
    2. Create AgentPipeline for the appropriate channel
    3. Poll messages from all incoming topics
    4. Parse each message into UnifiedMessage
    5. Run through agent pipeline
    6. Publish response or escalation to output topic
    7. On failure: retry up to max_retries, then dead letter
    8. Report metrics periodically
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        group_id: str = "taskflow-agent-workers",
        poll_interval_ms: int = 1000,
        metrics_interval_sec: int = 60,
        max_retries: int = 3,
    ):
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self.group_id = group_id
        self.poll_interval_ms = poll_interval_ms
        self.metrics_interval_sec = metrics_interval_sec
        self.max_retries = max_retries

        self.consumer: Optional[KafkaConsumerWrapper] = None
        self.producer: Optional[KafkaProducerWrapper] = None
        self.parser = MessageParser()
        self.metrics = ProcessingMetrics()
        self._running = False
        self._shutdown_event = None

        # Channel-specific pipelines (lazy-initialized)
        self._pipelines: dict[str, AgentPipeline] = {}

    def _get_pipeline(self, channel: str) -> AgentPipeline:
        """Get or create an AgentPipeline for the given channel."""
        if channel not in self._pipelines:
            logger.info("Creating AgentPipeline for channel: %s", channel)
            self._pipelines[channel] = AgentPipeline(channel=channel)
        return self._pipelines[channel]

    # ── Lifecycle ──

    async def start(self):
        """Start the message processor — initialize connections and begin polling."""
        logger.info("Starting UnifiedMessageProcessor...")
        self._running = True

        # Initialize Kafka connections
        self.consumer = KafkaConsumerWrapper(
            topics=KafkaTopics.ALL_INCOMING,
            group_id=self.group_id,
            bootstrap_servers=self.bootstrap_servers,
        )
        await self.consumer.initialize()

        self.producer = KafkaProducerWrapper(bootstrap_servers=self.bootstrap_servers)
        await self.producer.initialize()

        logger.info("UnifiedMessageProcessor started — polling topics: %s", KafkaTopics.ALL_INCOMING)

        # Main processing loop
        try:
            await self._processing_loop()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — shutting down")
        except Exception as exc:
            logger.critical("Fatal error in processing loop: %s", exc, exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Gracefully stop the message processor."""
        logger.info("Stopping UnifiedMessageProcessor...")
        self._running = False

        # Report final metrics
        summary = self.metrics.get_summary()
        logger.info("Final metrics: %s", json.dumps(summary, indent=2))

        # Close connections
        if self.consumer:
            await self.consumer.close()
        if self.producer:
            await self.producer.close()

        logger.info("UnifiedMessageProcessor stopped")

    async def _processing_loop(self):
        """Main loop: poll → parse → process → publish."""
        last_metrics_report = time.time()

        while self._running:
            try:
                # Poll for messages
                messages = await self.consumer.poll(timeout_ms=self.poll_interval_ms)

                for kafka_msg in messages:
                    await self._process_single_message(kafka_msg)

                # Periodic metrics report
                now = time.time()
                if now - last_metrics_report >= self.metrics_interval_sec:
                    summary = self.metrics.get_summary()
                    logger.info("Metrics: %s", json.dumps(summary))
                    last_metrics_report = now

            except Exception as exc:
                logger.error("Error in processing loop: %s", exc, exc_info=True)
                await self._safe_sleep(5)

    async def _safe_sleep(self, seconds: float):
        """Sleep without blocking the event loop."""
        import asyncio
        await asyncio.sleep(seconds)

    # ── Message Processing ──

    async def _process_single_message(self, kafka_msg: dict):
        """
        Process a single Kafka message through the full pipeline.

        Flow:
        1. Parse into UnifiedMessage
        2. Run through AgentPipeline
        3. Publish result to output topic
        4. On failure: retry or dead letter
        """
        start_time = time.time()
        topic = kafka_msg.get("topic", "unknown")
        offset = kafka_msg.get("offset", 0)

        try:
            # Step 1: Parse
            unified_msg = self.parser.parse(kafka_msg.get("value", {}), kafka_msg)
            unified_msg.status = ProcessingStatus.PROCESSING.value
            unified_msg.processing_started_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Processing %s from %s (offset: %d) — customer: %s, channel: %s",
                unified_msg.message_id, topic, offset,
                unified_msg.customer_name, unified_msg.channel,
            )

            # Step 2: Run agent pipeline
            pipeline = self._get_pipeline(unified_msg.channel)
            result = await pipeline.process_inquiry(
                customer_name=unified_msg.customer_name,
                message=unified_msg.content,
                email=unified_msg.customer_email,
                phone=unified_msg.customer_phone,
                subject=unified_msg.subject,
            )

            processing_time_ms = (time.time() - start_time) * 1000

            # Step 3: Build processing result
            processing_result = ProcessingResult(
                message_id=unified_msg.message_id,
                ticket_id=result.get("ticket_id"),
                customer_id=result.get("customer_id"),
                status=ProcessingStatus.COMPLETED.value,
                response_text=result.get("response", ""),
                escalation_needed=result.get("steps", {}).get("escalation", {}).get("escalate", False),
                escalation_team=result.get("steps", {}).get("escalation", {}).get("team", ""),
                escalation_sla=result.get("steps", {}).get("escalation", {}).get("sla", ""),
                processing_time_ms=processing_time_ms,
                pipeline_steps=result.get("steps", {}),
            )

            # Step 4: Determine output topic and publish
            if processing_result.escalation_needed:
                output_topic = KafkaTopics.OUTGOING_ESCALATIONS
                self.metrics.record_escalation()
            else:
                output_topic = KafkaTopics.OUTGOING_RESPONSES

            output_payload = {
                "processing_result": processing_result.to_dict(),
                "original_message": unified_msg.to_dict(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            processing_result.output_topic = output_topic
            processing_result.output_payload = output_payload

            await self.producer.send(
                topic=output_topic,
                payload=output_payload,
                key=unified_msg.message_id,
            )

            # Record metrics
            self.metrics.record_success(
                unified_msg.channel, topic, processing_time_ms,
            )

            logger.info(
                "Completed %s in %.0fms — ticket: %s, escalated: %s",
                unified_msg.message_id, processing_time_ms,
                processing_result.ticket_id, processing_result.escalation_needed,
            )

        except Exception as exc:
            processing_time_ms = (time.time() - start_time) * 1000
            error_type = type(exc).__name__
            error_msg = str(exc)

            logger.error(
                "Failed to process message from %s (offset: %d): %s — %s",
                topic, offset, error_type, error_msg,
            )

            # Retry logic with exponential backoff
            retry_count = kafka_msg.get("value", {}).get("retry_count", 0)
            if retry_count < self.max_retries:
                # Exponential backoff: 2^retry_count seconds
                backoff = 2 ** retry_count
                logger.info(
                    "Retrying message (attempt %d/%d) after %ds backoff",
                    retry_count + 1, self.max_retries, backoff,
                )
                await self._safe_sleep(backoff)

                # Re-publish to same topic with incremented retry count
                retry_payload = kafka_msg.get("value", {}).copy()
                retry_payload["retry_count"] = retry_count + 1
                retry_payload["last_error"] = error_msg
                retry_payload["retry_at"] = datetime.now(timezone.utc).isoformat()

                await self.producer.send(
                    topic=topic,
                    payload=retry_payload,
                    key=kafka_msg.get("key"),
                )
                self.metrics.record_retry()
            else:
                # Dead letter
                dead_letter_payload = {
                    "original_message": kafka_msg.get("value", {}),
                    "kafka_meta": {
                        "topic": topic,
                        "partition": kafka_msg.get("partition"),
                        "offset": offset,
                    },
                    "error_type": error_type,
                    "error_message": error_msg,
                    "retry_count": retry_count,
                    "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
                }
                await self.producer.send(
                    topic=KafkaTopics.ERRORS_DEAD_LETTER,
                    payload=dead_letter_payload,
                    key=kafka_msg.get("key"),
                )
                self.metrics.record_dead_letter()
                logger.warning(
                    "Dead lettered message from %s (offset: %d) after %d retries",
                    topic, offset, retry_count,
                )

            self.metrics.record_failure(unified_msg.channel if 'unified_msg' in locals() else "unknown", error_type)

    # ── Manual Processing (for testing / API-triggered) ──

    async def process_message(
        self,
        channel: str,
        payload: dict,
        kafka_meta: Optional[dict] = None,
    ) -> ProcessingResult:
        """
        Process a single message manually (bypassing Kafka consumer).

        Useful for testing, API-triggered processing, or replaying
        dead letter messages.

        Args:
            channel: Message channel (email, whatsapp, web_form).
            payload: Raw message payload dict.
            kafka_meta: Optional Kafka metadata (topic, partition, offset).

        Returns:
            ProcessingResult with full outcome.
        """
        kafka_meta = kafka_meta or {
            "topic": f"taskflow.incoming.{channel}",
            "partition": 0,
            "offset": 0,
            "key": None,
        }

        unified_msg = self.parser.parse(payload, kafka_meta)
        pipeline = self._get_pipeline(channel)

        start_time = time.time()
        result = await pipeline.process_inquiry(
            customer_name=unified_msg.customer_name,
            message=unified_msg.content,
            email=unified_msg.customer_email,
            phone=unified_msg.customer_phone,
            subject=unified_msg.subject,
        )

        processing_time_ms = (time.time() - start_time) * 1000

        processing_result = ProcessingResult(
            message_id=unified_msg.message_id,
            ticket_id=result.get("ticket_id"),
            customer_id=result.get("customer_id"),
            status=ProcessingStatus.COMPLETED.value if result.get("status") == "completed" else ProcessingStatus.FAILED.value,
            response_text=result.get("response", ""),
            escalation_needed=result.get("steps", {}).get("escalation", {}).get("escalate", False),
            escalation_team=result.get("steps", {}).get("escalation", {}).get("team", ""),
            escalation_sla=result.get("steps", {}).get("escalation", {}).get("sla", ""),
            processing_time_ms=processing_time_ms,
            pipeline_steps=result.get("steps", {}),
        )

        self.metrics.record_success(channel, kafka_meta.get("topic", ""), processing_time_ms)
        return processing_result

    # ── Health Check ──

    def get_health(self) -> dict:
        """Return worker health status."""
        return {
            "status": "healthy" if self._running else "stopped",
            "worker": "UnifiedMessageProcessor",
            "group_id": self.group_id,
            "topics": KafkaTopics.ALL_INCOMING,
            "metrics": self.metrics.get_summary(),
            "pipelines": list(self._pipelines.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ============================================================
# ENTRY POINT
# ============================================================

async def main():
    """Run the UnifiedMessageProcessor."""
    import asyncio

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    processor = UnifiedMessageProcessor(
        bootstrap_servers=getattr(settings, "kafka_bootstrap_servers", "localhost:9092"),
        group_id="taskflow-agent-workers",
        poll_interval_ms=1000,
        metrics_interval_sec=30,
        max_retries=3,
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def _shutdown_handler():
        asyncio.create_task(processor.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown_handler)

    await processor.start()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
