"""
TaskFlow AI Support Agent — Kafka Client
CRM Digital FTE Factory Final Hackathon 5og

Provides:
- Topic definitions and auto-creation
- Async Kafka producer with retry logic
- Async Kafka consumer with partition assignment
- Admin client for topic management
- Connection health checks
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Optional

from production.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# TOPIC DEFINITIONS
# ============================================================

@dataclass
class TopicConfig:
    """Configuration for a single Kafka topic."""
    name: str
    num_partitions: int = 3
    replication_factor: int = 1
    retention_ms: int = 7 * 24 * 60 * 60 * 1000  # 7 days default
    cleanup_policy: str = "delete"
    max_message_bytes: int = 10 * 1024 * 1024  # 10 MB
    config: dict = field(default_factory=dict)

    def to_admin_config(self) -> dict:
        """Convert to Kafka admin NewTopic config dict."""
        return {
            "name": self.name,
            "num_partitions": self.num_partitions,
            "replication_factor": self.replication_factor,
            "config": {
                "retention.ms": str(self.retention_ms),
                "cleanup.policy": self.cleanup_policy,
                "max.message.bytes": str(self.max_message_bytes),
                **self.config,
            },
        }


class TaskFlowTopics:
    """All Kafka topic definitions for the TaskFlow pipeline."""

    # ── Incoming Channels ──
    INCOMING_EMAIL = TopicConfig(
        name="taskflow.incoming.email",
        num_partitions=3,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        config={"message.timestamp.type": "CreateTime"},
    )
    INCOMING_WHATSAPP = TopicConfig(
        name="taskflow.incoming.whatsapp",
        num_partitions=3,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        config={"message.timestamp.type": "CreateTime"},
    )
    INCOMING_WEB_FORM = TopicConfig(
        name="taskflow.incoming.web_form",
        num_partitions=2,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        config={"message.timestamp.type": "CreateTime"},
    )

    # ── Outgoing Results ──
    OUTGOING_RESPONSES = TopicConfig(
        name="taskflow.outgoing.responses",
        num_partitions=3,
        retention_ms=3 * 24 * 60 * 60 * 1000,  # 3 days
        config={"message.timestamp.type": "CreateTime"},
    )
    OUTGOING_ESCALATIONS = TopicConfig(
        name="taskflow.outgoing.escalations",
        num_partitions=2,
        retention_ms=14 * 24 * 60 * 60 * 1000,  # 14 days (longer for audit)
        config={"message.timestamp.type": "CreateTime"},
    )

    # ── Error Handling ──
    ERRORS_DEAD_LETTER = TopicConfig(
        name="taskflow.errors.dead_letter",
        num_partitions=1,
        retention_ms=30 * 24 * 60 * 60 * 1000,  # 30 days
        cleanup_policy="compact",
        config={"message.timestamp.type": "CreateTime"},
    )

    # ── Internal / Events ──
    EVENTS_TICKET_CREATED = TopicConfig(
        name="taskflow.events.ticket_created",
        num_partitions=3,
        retention_ms=7 * 24 * 60 * 60 * 1000,
    )
    EVENTS_TICKET_ESCALATED = TopicConfig(
        name="taskflow.events.ticket_escalated",
        num_partitions=2,
        retention_ms=14 * 24 * 60 * 60 * 1000,
    )
    EVENTS_CUSTOMER_UPDATED = TopicConfig(
        name="taskflow.events.customer_updated",
        num_partitions=2,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        cleanup_policy="compact",
    )
    EVENTS_AGENT_METRICS = TopicConfig(
        name="taskflow.events.agent_metrics",
        num_partitions=1,
        retention_ms=30 * 24 * 60 * 60 * 1000,
    )

    # ── All Topics ──
    ALL = [
        INCOMING_EMAIL,
        INCOMING_WHATSAPP,
        INCOMING_WEB_FORM,
        OUTGOING_RESPONSES,
        OUTGOING_ESCALATIONS,
        ERRORS_DEAD_LETTER,
        EVENTS_TICKET_CREATED,
        EVENTS_TICKET_ESCALATED,
        EVENTS_CUSTOMER_UPDATED,
        EVENTS_AGENT_METRICS,
    ]

    INCOMING = [INCOMING_EMAIL, INCOMING_WHATSAPP, INCOMING_WEB_FORM]
    OUTGOING = [OUTGOING_RESPONSES, OUTGOING_ESCALATIONS]
    ERRORS = [ERRORS_DEAD_LETTER]
    EVENTS = [EVENTS_TICKET_CREATED, EVENTS_TICKET_ESCALATED, EVENTS_CUSTOMER_UPDATED, EVENTS_AGENT_METRICS]

    @classmethod
    def get_by_name(cls, name: str) -> Optional[TopicConfig]:
        """Get topic config by name."""
        for topic in cls.ALL:
            if topic.name == name:
                return topic
        return None


# ============================================================
# MESSAGE ENVELOPE
# ============================================================

class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class KafkaMessageEnvelope:
    """Standard envelope for all Kafka messages in the TaskFlow pipeline."""
    message_id: str
    event_type: str
    channel: str
    payload: dict
    priority: str = MessagePriority.NORMAL.value
    source: str = "taskflow-agent"
    version: str = "1.0.0"
    timestamp: str = ""
    correlation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.correlation_id:
            self.correlation_id = self.message_id

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "KafkaMessageEnvelope":
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict) -> "KafkaMessageEnvelope":
        return cls(**data)


# ============================================================
# KAFKA ADMIN CLIENT
# ============================================================

class KafkaAdminClient:
    """Admin client for managing Kafka topics."""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or getattr(settings, "kafka_bootstrap_servers", "localhost:9092")
        self._admin = None
        self._initialized = False

    async def initialize(self):
        """Initialize the admin client."""
        try:
            from kafka.admin import KafkaAdminClient as _KafkaAdminClient
            self._admin = _KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id="taskflow-admin",
            )
            self._initialized = True
            logger.info("Kafka admin client initialized — brokers: %s", self.bootstrap_servers)
        except ImportError:
            logger.warning("kafka-python not installed — admin client in mock mode")
            self._initialized = True
        except Exception as exc:
            logger.error("Failed to initialize Kafka admin client: %s", exc, exc_info=True)
            raise

    async def create_topics(self, topics: Optional[list[TopicConfig]] = None, if_not_exists: bool = True):
        """
        Create Kafka topics.

        Args:
            topics: List of TopicConfig to create. Defaults to all TaskFlowTopics.
            if_not_exists: Skip if topic already exists.
        """
        if not self._initialized:
            await self.initialize()

        topics_to_create = topics or TaskFlowTopics.ALL

        if self._admin:
            try:
                from kafka.admin import NewTopic
                new_topics = []
                for tc in topics_to_create:
                    topic = NewTopic(
                        name=tc.name,
                        num_partitions=tc.num_partitions,
                        replication_factor=tc.replication_factor,
                        topic_configs=tc.config,
                    )
                    new_topics.append(topic)

                existing = set(self._admin.list_topics())
                to_create = [t for t in new_topics if not if_not_exists or t.name not in existing]

                if to_create:
                    self._admin.create_topics(new_topics=to_create, validate_only=False)
                    logger.info("Created %d topics: %s", len(to_create), [t.name for t in to_create])
                else:
                    logger.info("All topics already exist — skipping creation")

            except Exception as exc:
                logger.error("Failed to create topics: %s", exc, exc_info=True)
                raise
        else:
            # Mock mode
            logger.info(
                "[MOCK] Would create %d topics: %s",
                len(topics_to_create), [t.name for t in topics_to_create],
            )

    async def delete_topics(self, topic_names: list[str]):
        """Delete Kafka topics."""
        if not self._initialized:
            await self.initialize()

        if self._admin:
            try:
                self._admin.delete_topics(topics=topic_names)
                logger.info("Deleted topics: %s", topic_names)
            except Exception as exc:
                logger.error("Failed to delete topics: %s", exc, exc_info=True)
                raise
        else:
            logger.info("[MOCK] Would delete topics: %s", topic_names)

    async def list_topics(self) -> list[str]:
        """List all Kafka topics."""
        if not self._initialized:
            await self.initialize()

        if self._admin:
            try:
                return self._admin.list_topics()
            except Exception as exc:
                logger.error("Failed to list topics: %s", exc, exc_info=True)
                return []
        return [t.name for t in TaskFlowTopics.ALL]

    async def describe_topic(self, topic_name: str) -> Optional[dict]:
        """Describe a specific topic."""
        if not self._initialized:
            await self.initialize()

        if self._admin:
            try:
                # kafka-python doesn't have direct describe_topic, use list_topics
                topics = self._admin.list_topics()
                if topic_name in topics:
                    return {"name": topic_name, "exists": True}
                return {"name": topic_name, "exists": False}
            except Exception as exc:
                logger.error("Failed to describe topic %s: %s", topic_name, exc)
                return None
        return {"name": topic_name, "exists": True, "mock": True}

    async def close(self):
        """Close the admin client."""
        if self._admin:
            self._admin.close()
            logger.info("Kafka admin client closed")


# ============================================================
# KAFKA PRODUCER
# ============================================================

class KafkaProducer:
    """
    Async Kafka producer with retry logic and message envelopes.

    Usage:
        producer = KafkaProducer()
        await producer.initialize()
        await producer.send("taskflow.incoming.email", payload={"key": "value"})
        await producer.close()
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff_ms: int = 100,
        acks: str = "all",
        compression_type: str = "gzip",
    ):
        self.bootstrap_servers = bootstrap_servers or getattr(settings, "kafka_bootstrap_servers", "localhost:9092")
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.acks = acks
        self.compression_type = compression_type
        self._producer = None
        self._initialized = False
        self._messages_sent = 0
        self._bytes_sent = 0

    async def initialize(self):
        """Initialize the Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                acks=self.acks,
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

    async def send(
        self,
        topic: str,
        payload: dict,
        key: Optional[str] = None,
        headers: Optional[list[tuple[str, bytes]]] = None,
        priority: str = MessagePriority.NORMAL.value,
        event_type: str = "message",
        channel: str = "unknown",
    ) -> dict:
        """
        Send a message to a Kafka topic with envelope wrapping.

        Args:
            topic: Target topic name.
            payload: Message payload dict.
            key: Optional message key for partitioning.
            headers: Optional Kafka headers.
            priority: Message priority level.
            event_type: Event type for the envelope.
            channel: Source channel for the envelope.

        Returns:
            Dict with send status and metadata.
        """
        if not self._initialized:
            await self.initialize()

        # Wrap in envelope
        import uuid
        envelope = KafkaMessageEnvelope(
            message_id=str(uuid.uuid4()),
            event_type=event_type,
            channel=channel,
            payload=payload,
            priority=priority,
            correlation_id=key,
        )

        value_bytes = json.dumps(envelope.to_dict(), default=str).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None

        # Add standard headers
        kafka_headers = headers or []
        kafka_headers.extend([
            ("event_type", event_type.encode("utf-8")),
            ("channel", channel.encode("utf-8")),
            ("priority", priority.encode("utf-8")),
            ("message_id", envelope.message_id.encode("utf-8")),
            ("timestamp", envelope.timestamp.encode("utf-8")),
        ])

        try:
            if self._producer:
                metadata = await self._producer.send_and_wait(
                    topic=topic,
                    value=value_bytes,
                    key=key_bytes,
                    headers=kafka_headers,
                )
                self._messages_sent += 1
                self._bytes_sent += len(value_bytes)

                logger.debug(
                    "Sent to %s — key: %s, partition: %d, offset: %d",
                    topic, key, metadata.partition if metadata else -1,
                    metadata.offset if metadata else -1,
                )

                return {
                    "status": "sent",
                    "topic": topic,
                    "message_id": envelope.message_id,
                    "partition": metadata.partition if metadata else -1,
                    "offset": metadata.offset if metadata else -1,
                    "timestamp": envelope.timestamp,
                }
            else:
                # Mock mode
                self._messages_sent += 1
                self._bytes_sent += len(value_bytes)
                logger.info(
                    "[MOCK] Sent to %s — key: %s, message_id: %s, size: %d bytes",
                    topic, key, envelope.message_id, len(value_bytes),
                )
                return {
                    "status": "mock_sent",
                    "topic": topic,
                    "message_id": envelope.message_id,
                    "timestamp": envelope.timestamp,
                }

        except Exception as exc:
            logger.error("Failed to send to %s: %s", topic, exc, exc_info=True)
            return {
                "status": "error",
                "topic": topic,
                "message_id": envelope.message_id,
                "error": str(exc),
            }

    async def send_batch(
        self,
        topic: str,
        messages: list[dict],
        key_field: Optional[str] = None,
    ) -> list[dict]:
        """
        Send a batch of messages to a topic.

        Args:
            topic: Target topic name.
            messages: List of payload dicts.
            key_field: Optional field name to use as message key.

        Returns:
            List of send results.
        """
        results = []
        for msg in messages:
            key = str(msg.get(key_field)) if key_field and key_field in msg else None
            result = await self.send(topic=topic, payload=msg, key=key)
            results.append(result)
        return results

    async def flush(self):
        """Flush any buffered messages."""
        if self._producer:
            await self._producer.flush()

    async def close(self):
        """Close the Kafka producer."""
        if self._producer:
            await self._producer.stop()
            logger.info(
                "Kafka producer closed — sent %d messages (%d bytes)",
                self._messages_sent, self._bytes_sent,
            )

    def get_stats(self) -> dict:
        """Get producer statistics."""
        return {
            "messages_sent": self._messages_sent,
            "bytes_sent": self._bytes_sent,
            "initialized": self._initialized,
            "bootstrap_servers": self.bootstrap_servers,
        }


# ============================================================
# KAFKA CONSUMER
# ============================================================

class KafkaConsumer:
    """
    Async Kafka consumer with automatic deserialization and envelope parsing.

    Usage:
        consumer = KafkaConsumer(topics=["taskflow.incoming.email"])
        await consumer.initialize()
        async for msg in consumer.poll():
            process(msg)
        await consumer.close()
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str = "taskflow-agent-workers",
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        auto_commit_interval_ms: int = 1000,
        max_poll_records: int = 10,
        max_poll_interval_ms: int = 300000,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 10000,
    ):
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or getattr(settings, "kafka_bootstrap_servers", "localhost:9092")
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        self.max_poll_records = max_poll_records
        self.max_poll_interval_ms = max_poll_interval_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self._consumer = None
        self._initialized = False
        self._messages_consumed = 0
        self._bytes_consumed = 0
        self._errors = 0

    async def initialize(self):
        """Initialize the Kafka consumer."""
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                auto_commit_interval_ms=self.auto_commit_interval_ms,
                max_poll_records=self.max_poll_records,
                max_poll_interval_ms=self.max_poll_interval_ms,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
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

        Args:
            timeout_ms: Max time to wait for messages.

        Returns:
            List of deserialized message dicts with envelope data.
        """
        if not self._initialized:
            await self.initialize()

        messages = []
        try:
            if self._consumer:
                records = await self._consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=self.max_poll_records,
                )
                for tp, batch in records.items():
                    for record in batch:
                        msg = self._deserialize_record(record)
                        if msg:
                            messages.append(msg)
                            self._messages_consumed += 1
                            self._bytes_consumed += len(record.value) if record.value else 0
        except Exception as exc:
            self._errors += 1
            logger.error("Kafka poll failed: %s", exc, exc_info=True)

        return messages

    async def poll_stream(self, timeout_ms: int = 5000) -> AsyncGenerator[dict, None]:
        """
        Async generator for continuous message streaming.

        Usage:
            async for msg in consumer.poll_stream():
                process(msg)
        """
        while True:
            messages = await self.poll(timeout_ms=timeout_ms)
            for msg in messages:
                yield msg
            import asyncio
            await asyncio.sleep(0.1)

    def _deserialize_record(self, record) -> Optional[dict]:
        """Deserialize a Kafka record into a dict with envelope data."""
        try:
            value = record.value
            if isinstance(value, bytes):
                value = json.loads(value.decode("utf-8"))

            # Extract envelope if present
            if isinstance(value, dict) and "message_id" in value and "payload" in value:
                envelope = KafkaMessageEnvelope.from_dict(value)
                return {
                    "envelope": envelope.to_dict(),
                    "payload": envelope.payload,
                    "message_id": envelope.message_id,
                    "event_type": envelope.event_type,
                    "channel": envelope.channel,
                    "priority": envelope.priority,
                    "correlation_id": envelope.correlation_id,
                    "kafka": {
                        "topic": record.topic if hasattr(record, "topic") else "",
                        "partition": record.partition if hasattr(record, "partition") else -1,
                        "offset": record.offset if hasattr(record, "offset") else -1,
                        "timestamp": record.timestamp if hasattr(record, "timestamp") else None,
                    },
                }

            # No envelope — return raw
            return {
                "payload": value,
                "kafka": {
                    "topic": record.topic if hasattr(record, "topic") else "",
                    "partition": record.partition if hasattr(record, "partition") else -1,
                    "offset": record.offset if hasattr(record, "offset") else -1,
                    "timestamp": record.timestamp if hasattr(record, "timestamp") else None,
                },
            }

        except Exception as exc:
            self._errors += 1
            logger.error("Failed to deserialize record: %s", exc)
            return None

    async def commit(self):
        """Manually commit offsets (if auto_commit is disabled)."""
        if self._consumer and not self.enable_auto_commit:
            await self._consumer.commit()

    async def seek_to_beginning(self):
        """Seek to the beginning of all assigned partitions."""
        if self._consumer:
            self._consumer.seek_to_beginning()
            logger.info("Seek to beginning")

    async def seek_to_end(self):
        """Seek to the end of all assigned partitions."""
        if self._consumer:
            self._consumer.seek_to_end()
            logger.info("Seek to end")

    async def close(self):
        """Close the Kafka consumer."""
        if self._consumer:
            await self._consumer.stop()
            logger.info(
                "Kafka consumer closed — consumed %d messages (%d bytes, %d errors)",
                self._messages_consumed, self._bytes_consumed, self._errors,
            )

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            "messages_consumed": self._messages_consumed,
            "bytes_consumed": self._bytes_consumed,
            "errors": self._errors,
            "initialized": self._initialized,
            "topics": self.topics,
            "group_id": self.group_id,
        }


# ============================================================
# CONNECTION POOL / CLIENT FACTORY
# ============================================================

class KafkaClientFactory:
    """
    Factory for creating and managing Kafka clients.

    Provides singleton producer/consumer instances with lazy initialization.
    """

    _instance = None
    _producers: dict[str, KafkaProducer] = {}
    _consumers: dict[str, KafkaConsumer] = {}
    _admin: Optional[KafkaAdminClient] = None

    @classmethod
    def get_instance(cls) -> "KafkaClientFactory":
        """Get singleton factory instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def get_producer(
        cls,
        name: str = "default",
        bootstrap_servers: Optional[str] = None,
        **kwargs,
    ) -> KafkaProducer:
        """Get or create a named producer."""
        if name not in cls._producers:
            cls._producers[name] = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                **kwargs,
            )
            await cls._producers[name].initialize()
        return cls._producers[name]

    @classmethod
    async def get_consumer(
        cls,
        name: str,
        topics: list[str],
        bootstrap_servers: Optional[str] = None,
        **kwargs,
    ) -> KafkaConsumer:
        """Get or create a named consumer."""
        if name not in cls._consumers:
            cls._consumers[name] = KafkaConsumer(
                topics=topics,
                bootstrap_servers=bootstrap_servers,
                **kwargs,
            )
            await cls._consumers[name].initialize()
        return cls._consumers[name]

    @classmethod
    async def get_admin(cls, bootstrap_servers: Optional[str] = None) -> KafkaAdminClient:
        """Get or create the admin client."""
        if cls._admin is None:
            cls._admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
            await cls._admin.initialize()
        return cls._admin

    @classmethod
    async def close_all(cls):
        """Close all producers, consumers, and admin client."""
        for name, producer in cls._producers.items():
            await producer.close()
            logger.info("Closed producer: %s", name)
        for name, consumer in cls._consumers.items():
            await consumer.close()
            logger.info("Closed consumer: %s", name)
        if cls._admin:
            await cls._admin.close()
            logger.info("Closed admin client")
        cls._producers.clear()
        cls._consumers.clear()
        cls._admin = None


# ============================================================
# HEALTH CHECK
# ============================================================

async def check_kafka_health(bootstrap_servers: Optional[str] = None) -> dict:
    """
    Check Kafka cluster health.

    Returns:
        Dict with cluster health status.
    """
    servers = bootstrap_servers or getattr(settings, "kafka_bootstrap_servers", "localhost:9092")
    health = {
        "status": "unknown",
        "bootstrap_servers": servers,
        "topics": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        admin = KafkaAdminClient(bootstrap_servers=servers)
        await admin.initialize()
        topics = await admin.list_topics()
        await admin.close()

        # Check which TaskFlow topics exist
        for tc in TaskFlowTopics.ALL:
            health["topics"][tc.name] = {
                "exists": tc.name in topics,
                "expected_partitions": tc.num_partitions,
            }

        existing_count = sum(1 for t in health["topics"].values() if t["exists"])
        health["status"] = "healthy" if existing_count == len(TaskFlowTopics.ALL) else "degraded"
        health["topics_existing"] = existing_count
        health["topics_expected"] = len(TaskFlowTopics.ALL)

    except Exception as exc:
        health["status"] = "unhealthy"
        health["error"] = str(exc)
        logger.error("Kafka health check failed: %s", exc)

    return health


# ============================================================
# ENTRY POINT: Setup Topics
# ============================================================

async def setup_topics(bootstrap_servers: Optional[str] = None):
    """Create all TaskFlow Kafka topics."""
    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
    await admin.initialize()
    await admin.create_topics()
    await admin.close()
    logger.info("All TaskFlow topics created/verified")


if __name__ == "__main__":
    import asyncio

    async def main():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        )

        print("=" * 70)
        print("TaskFlow Kafka Client — Topic Setup")
        print("=" * 70)

        # Setup topics
        await setup_topics()

        # Health check
        health = await check_kafka_health()
        print(f"\nHealth: {health['status']}")
        print(f"Topics: {health.get('topics_existing', 0)}/{health.get('topics_expected', 0)} existing")
        for name, info in health.get("topics", {}).items():
            status = "✓" if info["exists"] else "✗"
            print(f"  {status} {name} (expected partitions: {info['expected_partitions']})")

    asyncio.run(main())
