import os

from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://driver:driver@localhost:5432/driversafety"
)

TOPIC_RAW = "telemetry.raw"
TOPIC_DLQ = "telemetry.dlq"
TOPIC_ALERTS = "alerts"

DEDUP_TTL_S = int(os.getenv("DEDUP_TTL_S", "600"))
ALERT_WINDOW_S = int(os.getenv("ALERT_WINDOW_S", "120"))
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "4"))
ALERT_COOLDOWN_S = int(os.getenv("ALERT_COOLDOWN_S", "300"))

CLICKHOUSE_USER = os.getenv("CH_USER", "ch")
CLICKHOUSE_PASSWORD = os.getenv("CH_PASSWORD", "ch")
API_CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
)
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")