from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from web.models import Base

os.makedirs("data", exist_ok=True)
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/yun.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE schedules ADD COLUMN random_delay_minutes INTEGER DEFAULT 0"))
    except Exception:
        pass
