"""
TaskFlow AI Support Agent — FastAPI Application
CRM Digital FTE Factory Final Hackathon 5

Modified for SQLite Synchronous compatibility.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, EmailStr, Field

from production.config.settings import get_settings
from production.config.logging import setup_logging
from production.agent.customer_success_agent import AgentPipeline
from production.channels.gmail_handler import GmailHandler
from production.channels.whatsapp_handler import WhatsAppHandler
from production.database.session import get_session_factory, init_db, close_db
from production.kafka_client import KafkaProducer

# Setup
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# Global state
_kafka_producer = None
_gmail_handler: GmailHandler | None = None
_whatsapp_handler: WhatsAppHandler | None = None

# Global pipeline cache
_pipeline_cache: dict = {}

def _get_pipeline(channel: str = "web_form") -> AgentPipeline:
    if channel not in _pipeline_cache:
        _pipeline_cache[channel] = AgentPipeline(channel=channel)
        logger.info(f"AgentPipeline created for channel: {channel}")
    return _pipeline_cache[channel]


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _kafka_producer, _gmail_handler, _whatsapp_handler

    logger.info("TaskFlow AI Support Agent starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"OpenAI API Key: {'***' + settings.openai_api_key[-4:] if settings.openai_api_key and settings.openai_api_key != 'sk-your-openai-api-key-here' else 'NOT SET (mock mode)'}")

    # Initialize SQLAlchemy engine & session factory
    try:
        init_db()
        logger.info("Database tables initialized — SQLite ready")
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")

    # Initialize Kafka producer
    if settings.enable_kafka:
        try:
            _kafka_producer = KafkaProducer()
            await _kafka_producer.initialize()
            logger.info("Kafka producer initialized")
        except Exception as exc:
            logger.warning(f"Failed to init Kafka producer (optional): {exc}")
            _kafka_producer = None
    else:
        logger.info("Kafka disabled via settings")
        _kafka_producer = None

    # Initialize channel handlers
    _gmail_handler = GmailHandler()
    _whatsapp_handler = WhatsAppHandler()

    app.state.kafka_producer = _kafka_producer

    yield

    # Shutdown
    close_db()
    if _kafka_producer:
        await _kafka_producer.close()
        logger.info("Kafka producer closed")
    logger.info("TaskFlow AI Support Agent shutting down...")


app = FastAPI(
    title="TaskFlow AI Support Agent API",
    description="Customer Success AI Agent for TaskFlow SaaS",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration:.0f}ms)")
    return response


# Health checks
@app.get("/health", tags=["System"])
async def health_check():
    checks = {"db": "error", "kafka": "error"}

    # DB check
    try:
        from production.database.session import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error(f"Health check DB failed: {exc}")
        checks["db"] = "error"

    # Kafka check
    if _kafka_producer and getattr(_kafka_producer, "_initialized", False):
        checks["kafka"] = "ok"
    else:
        checks["kafka"] = "optional"

    status = "healthy" if checks["db"] == "ok" else "degraded"
    return {
        "status": status,
        "service": "taskflow-support-agent",
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# WhatsApp Demo Page
@app.get("/demo/whatsapp", tags=["Demo"])
async def whatsapp_demo():
    try:
        with open("whatsapp_demo.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading demo: {e}</h1>", status_code=500)


# Web Form Demo Page
@app.get("/demo/webform", tags=["Demo"])
async def webform_demo():
    try:
        with open("web_form_demo.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading demo: {e}</h1>", status_code=500)


# Pydantic Model for Web Form
class WebFormTicketRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr = Field(...)
    subject: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1, max_length=10000)
    category: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default="P3")


# Main Endpoint - Web Form Ticket
@app.post("/api/tickets", tags=["Channels", "Web Form"])
async def create_web_form_ticket(request: WebFormTicketRequest):
    logger.info(f"New ticket request from {request.customer_name} ({request.email})")

    try:
        pipeline = _get_pipeline(channel="web_form")

        result = await pipeline.process_inquiry(
            customer_name=request.customer_name,
            message=request.message,
            email=request.email,
            subject=request.subject,
        )

        if result.get("status") != "completed":
            raise HTTPException(status_code=500, detail="Agent processing failed")

        ticket_id = result.get("ticket_id", "TICKET-UNKNOWN")
        ai_response = result.get("response", "Thank you for your message. Our team will respond shortly.")

        # Save to SQLite
        try:
            from production.database.repositories import (
                CustomerRepository, TicketRepository, ConversationRepository, MessageRepository
            )
            
            factory = get_session_factory()
            with factory() as db:
                # Resolve or create customer
                customer_repo = CustomerRepository(db)
                customer = customer_repo.resolve_or_create(
                    name=request.customer_name,
                    email=request.email,
                )

                # Create ticket
                ticket_repo = TicketRepository(db)
                ticket = ticket_repo.create(
                    customer_id=customer.customer_id,
                    channel="web_form",
                    message=request.message,
                    subject=request.subject,
                    topic=result.get("steps", {}).get("knowledge_base", {}).get("results", [{}])[0].get("topic") if result.get("steps", {}).get("knowledge_base", {}).get("results") else None,
                    sentiment_score=result.get("steps", {}).get("sentiment", {}).get("score", 0),
                    sentiment_label=result.get("steps", {}).get("sentiment", {}).get("label", "neutral"),
                )

                # Create conversation turn
                conv_repo = ConversationRepository(db)
                conv = conv_repo.create_turn(
                    customer_id=customer.customer_id,
                    ticket_id=ticket.ticket_id,
                    channel="web_form",
                    topic=ticket.topic,
                    sentiment_score=ticket.sentiment_score,
                    sentiment_label=ticket.sentiment_label,
                    resolution_status="new",
                )

                # Record customer message
                msg_repo = MessageRepository(db)
                msg_repo.create(
                    conversation_id=str(conv.conversation_id),
                    ticket_id=ticket.ticket_id,
                    role="customer",
                    content=request.message,
                    channel="web_form",
                )

                # Record AI response message
                msg_repo.create(
                    conversation_id=str(conv.conversation_id),
                    ticket_id=ticket.ticket_id,
                    role="agent",
                    content=ai_response,
                    channel="web_form",
                    agent_name="TaskFlow AI Agent",
                )

                # Update ticket status
                ticket_repo.update_status(ticket.ticket_id, "responded")
                db_ticket_id = ticket.ticket_id

            logger.info(f"Ticket saved to DB: {db_ticket_id}")
        except Exception as db_exc:
            logger.error(f"Failed to save ticket to DB: {db_exc}", exc_info=True)
            db_ticket_id = ticket_id

        return JSONResponse(
            status_code=201,
            content={
                "status": "created",
                "ticket_id": db_ticket_id,
                "customer_name": request.customer_name,
                "email": request.email,
                "subject": request.subject,
                "priority": request.priority,
                "sla": "4 hours",
                "ai_response": ai_response,
                "message": "Your ticket has been created successfully. Our AI agent has responded below."
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ticket creation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create ticket. Please try again.")


@app.get("/api/tickets/{ticket_id}", tags=["Tickets"])
async def get_ticket(ticket_id: str):
    from production.database.repositories import TicketRepository
    
    factory = get_session_factory()
    with factory() as db:
        repo = TicketRepository(db)
        ticket = repo.find_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return {
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
            "subject": ticket.subject,
            "message": ticket.message,
            "created_at": ticket.created_at.isoformat(),
            "customer": {
                "name": ticket.customer.name,
                "email": ticket.customer.email,
            }
        }


@app.get("/api/customers", tags=["Customers"])
async def get_customer(email: str):
    from production.database.repositories import CustomerRepository
    
    factory = get_session_factory()
    with factory() as db:
        repo = CustomerRepository(db)
        customer = repo.find_by_email(email)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "total_tickets": customer.total_tickets,
            "created_at": customer.created_at.isoformat(),
        }


# ── Gmail Webhook ──
class GmailWebhookPayload(BaseModel):
    data: str
    attributes: dict = {}

@app.post("/webhooks/gmail", tags=["Channels", "Gmail"])
async def gmail_webhook(payload: GmailWebhookPayload):
    try:
        if not _gmail_handler:
            raise HTTPException(status_code=503, detail="Gmail handler not initialized")

        pubsub_message = {"data": payload.data, "attributes": payload.attributes}
        result = _gmail_handler.process_webhook(pubsub_message)

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        if result.get("status") == "skipped":
            return {"status": "skipped", "message": result.get("message")}

        # Run through pipeline if email parsed
        email_data = result.get("email", {})
        if email_data:
            pipeline = _get_pipeline(channel="email")
            agent_result = await pipeline.process_inquiry(
                customer_name=email_data.get("from_name", ""),
                message=email_data.get("body", ""),
                email=email_data.get("from_email"),
                subject=email_data.get("subject"),
            )
            
            ai_response = agent_result.get("response", "Thank you for your email. We have received your inquiry.")
            
            # Send reply back via Gmail
            _gmail_handler.send_reply(
                to_email=email_data.get("from_email"),
                subject=f"Re: {email_data.get('subject', 'Support Inquiry')}",
                body=ai_response,
                thread_id=email_data.get("gmail_thread_id"),
                in_reply_to=email_data.get("message_id")
            )

            result["ticket_id"] = agent_result.get("ticket_id")
            result["ai_response"] = ai_response

        logger.info(f"Gmail webhook processed — status: {result.get('status')}")
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Gmail webhook failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gmail webhook processing failed")


# ── WhatsApp Webhook Verification (GET) ──
@app.get("/webhooks/whatsapp", tags=["Channels", "WhatsApp"])
async def whatsapp_webhook_verify(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    challenge = WhatsAppHandler.verify_webhook_token(
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
    )
    if challenge:
        return int(challenge) if challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="Verification failed")


# ── WhatsApp Webhook (POST) ──
class WhatsAppWebhookPayload(BaseModel):
    object: str = "whatsapp_business_account"
    entry: list[dict] = []

@app.post("/webhooks/whatsapp", tags=["Channels", "WhatsApp"])
async def whatsapp_webhook(payload: WhatsAppWebhookPayload):
    try:
        if not _whatsapp_handler:
            raise HTTPException(status_code=503, detail="WhatsApp handler not initialized")

        messages = _whatsapp_handler.process_webhook(payload.model_dump())

        results = []
        for msg in messages:
            if msg.get("status") == "error":
                results.append(msg)
                continue

            pipeline = _get_pipeline(channel="whatsapp")
            agent_result = await pipeline.process_inquiry(
                customer_name=msg.get("sender_name", ""),
                message=msg.get("content", ""),
                phone=msg.get("sender_phone"),
            )
            
            ai_response = agent_result.get("response", "Thank you for your message. Our team will help you shortly.")
            
            # Send reply back to WhatsApp
            await _whatsapp_handler.send_text_reply(
                recipient_phone=msg.get("sender_phone"),
                text=ai_response
            )

            results.append({
                "sender": msg.get("sender_phone"),
                "ticket_id": agent_result.get("ticket_id"),
                "ai_response": ai_response,
                "status": "processed",
            })

        logger.info(f"WhatsApp webhook processed {len(results)} message(s)")
        return {"status": "success", "messages_processed": len(results), "results": results}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"WhatsApp webhook failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="WhatsApp webhook processing failed")


# Entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "production.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )