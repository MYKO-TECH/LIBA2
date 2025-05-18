import os
import logging
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------- Load .env ----------------
load_dotenv()

# ---------------- Settings ----------------
class Settings(BaseModel):
    version: str = "1.0.0"         # <─ Added version field

    # Required configurations
    TELEGRAM_TOKEN: str
    OPENAI_API_KEY: str
    ADMIN_ID: str
    WEBHOOK_SECRET: str
    ENCRYPT_KEY: str

    # Optional configurations with defaults
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT: int = 5               # Requests per minute
    SESSION_TTL: int = 3600           # 1 hour in seconds
    MAX_TOKENS: int = 300
    API_TIMEOUT: int = 30
    WEB_PORT: int = 8080
    DEBUG: bool = False

    # Security configurations
    CONTENT_MODERATION: bool = True
    SANITIZE_INPUT: bool = True


try:
    # Validate environment variables
    config = Settings(**os.environ)

    # Initialize encryption
    cipher = Fernet(config.ENCRYPT_KEY.encode())

    # Set debug mode verbosity if requested
    if config.DEBUG:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")

except ValidationError as e:
    logger.error(f"Configuration validation error: {e}")
    raise RuntimeError("Invalid configuration") from e
except ValueError as e:
    logger.error(f"Encryption initialization error: {e}")
    raise RuntimeError("Invalid encryption key") from e
