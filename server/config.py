"""Server configuration for flood agent frontend"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Server configuration settings"""

    # Server
    host: str = "127.0.0.1"
    port: int = 8766

    # Paths
    project_root: Path = Path(__file__).parent.parent
    outputs_dir: Path = project_root / "outputs"
    frontend_dir: Path = project_root / "frontend"

    # WebSocket
    ws_heartbeat_interval: int = 30
    ws_message_queue_size: int = 100
    max_connections: int = 50

    # CORS
    cors_origins: list[str] = ["http://127.0.0.1:8766", "http://localhost:8766"]

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"  # Ignore extra fields from .env
    )


settings = Settings()
