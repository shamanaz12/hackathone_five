"""
TaskFlow AI Support Agent — Settings
Production package for the CRM Digital FTE Factory Final Hackathon 5.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env file path relative to project root
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"

# Load .env file explicitly (override system env vars)
if _env_file.exists():
    load_dotenv(_env_file, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_env_file) if _env_file.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──
    app_name: str = "TaskFlow AI Support Agent"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # ── Database ──
    database_url: str = "postgresql://postgres:balaj786@localhost:5432/taskflow"
    database_async_url: str = "postgresql+asyncpg://postgres:balaj786@localhost:5432/taskflow"
    postgres_user: str = "postgres"
    postgres_password: str = "balaj786"
    postgres_db: str = "taskflow"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ── CORS ──
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "https://app.techcorp.com"]

    # ── Logging ──
    log_level: str = "INFO"
    log_format: str = "json"

    # ── Gmail / Email Channel ──
    gmail_project_id: str = ""
    gmail_pubsub_topic: str = "projects/taskflow-support/topics/gmail-support"
    gmail_service_account_file: str = ""
    support_email: str = "support@techcorp.com"

    # ── WhatsApp Channel ──
    whatsapp_verify_token: str = "techcorp-whatsapp-verify-2026"
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_api_version: str = "v18.0"

    # ── OpenAI / Agent ──
    openai_api_key: str = ""
    gemini_api_key: str = ""
    cohere_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    agent_temperature: float = 0.3
    agent_max_tokens: int = 2000

    # ── Rate Limiting ──
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # ── Feature Flags ──
    enable_kafka: bool = False
    enable_email_channel: bool = True
    enable_whatsapp_channel: bool = True
    enable_web_form: bool = True
    enable_agent_auto_resolve: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — reload on app restart."""
    return Settings()
