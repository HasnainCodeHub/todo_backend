"""Configuration module for MCP Server and AI Chatbot."""

import os
from pydantic import Field
from pydantic_settings import BaseSettings


def _default_mcp_server_url() -> str:
    """Compute default MCP server URL with Vercel auto-detection.

    Called only when MCP_SERVER_URL is not set in environment or .env file.

    VERCEL_URL is deployment-specific and changes on every deploy. Preview
    deployments at that URL are protected by Vercel Authentication, causing
    401 errors when the agent tries to connect to the MCP endpoint.

    VERCEL_PROJECT_PRODUCTION_URL is the stable production alias (e.g.
    todo-backend-xi-eosin.vercel.app) and is NOT gated by Vercel Auth.
    Always prefer it over VERCEL_URL.
    """
    # Stable production URL — present on all Vercel deployments since late 2023.
    production_url = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "")
    if production_url:
        return f"https://{production_url}/mcp"
    # Deployment-specific URL — only use as last resort (may trigger Vercel Auth).
    vercel_url = os.getenv("VERCEL_URL", "")
    if vercel_url:
        return f"https://{vercel_url}/mcp"
    return "http://localhost:8000/mcp"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database configuration
    database_url: str = os.getenv("DATABASE_URL", "")

    # JWT configuration
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    # Rate limiting configuration
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # in seconds

    # Application configuration
    app_name: str = "MCP Server for Task Management"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # AI Chatbot configuration (Phase 3)
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    chat_model: str = os.getenv("CHAT_MODEL", "gemini-2.5-flash")
    chat_context_limit: int = int(os.getenv("CHAT_CONTEXT_LIMIT", "20"))

    # MCP Server URL — pydantic-settings reads MCP_SERVER_URL from env/.env;
    # falls back to _default_mcp_server_url() which auto-detects Vercel URL.
    mcp_server_url: str = Field(default_factory=_default_mcp_server_url)

    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()
