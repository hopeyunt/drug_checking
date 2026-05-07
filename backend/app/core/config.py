from decimal import Decimal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/drugcheck"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    CHECK_COST: Decimal = Decimal("5")
    WELCOME_BONUS: Decimal = Decimal("50")

    MODEL_PATH: str = "/ml/interaction_model.joblib"
    GRLS_API_KEY: str = ""

    # Loyalty: Bronze=0%, Silver=5%, Gold=15%
    LOYALTY_SILVER_THRESHOLD: int = 50
    LOYALTY_GOLD_THRESHOLD: int = 200

    # ЮКасса (платёжный шлюз)
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "http://localhost:8501"

    # CORS — разрешённые домены (через запятую)
    # Пример: http://localhost:8501,https://drugcheck.ru
    ALLOWED_ORIGINS: str = "http://localhost:8501,http://localhost:3000"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
