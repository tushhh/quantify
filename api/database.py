import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("quantify.api.database")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/quantify.db")

# If using SQLite locally, create the directory
if DATABASE_URL.startswith("sqlite"):
    os.makedirs("./data", exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Cloud PostgreSQL (Render/Supabase)
    # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_trade_columns() -> None:
    """Ensure optional trade columns exist for hold health tracking."""
    ddl = [
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS alerted_at TIMESTAMP",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS hold_unit VARCHAR(16) DEFAULT 'days'",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS hold_value INTEGER DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS last_health_check_at TIMESTAMP",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS last_health_strength FLOAT",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS last_health_reason VARCHAR(512)",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS last_health_alert_at TIMESTAMP",
    ]
    try:
        with engine.begin() as conn:
            for stmt in ddl:
                try:
                    conn.execute(text(stmt))
                    log.info(f"✅ Migration executed: {stmt[:60]}...")
                except Exception as e:
                    log.warning(f"Migration statement failed (may already exist): {stmt[:60]}... | Error: {e}")
        log.info("✅ All trade columns verified/created successfully")
    except Exception as e:
        log.error(f"❌ Failed to run trade migrations: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
