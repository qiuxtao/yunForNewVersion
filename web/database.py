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
    
    # 兼容老版本库：加入无缝分组与启用的布尔值标识
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE schedules ADD COLUMN group_id VARCHAR"))
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE schedules ADD COLUMN is_active BOOLEAN DEFAULT 1"))
    except Exception:
        pass
        
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE schedules ADD COLUMN group_name VARCHAR(50) DEFAULT '未命名任务组'"))
    except Exception:
        pass
        
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            # 对于历史纯个体独立任务，打上一个独一无二的随机标识将它们转换为单人团模式
            conn.execute(text("UPDATE schedules SET group_id = lower(hex(randomblob(16))) WHERE group_id IS NULL OR group_id = ''"))
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE schedules ADD COLUMN run_days VARCHAR(50) DEFAULT '1,2,3,4,5,6,7'"))
    except Exception:
        pass
        
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN school_id VARCHAR DEFAULT '195'"))
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN school_host VARCHAR DEFAULT 'http://47.99.163.239:8080'"))
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN school_name VARCHAR DEFAULT '安徽邮电职业技术学院'"))
    except Exception:
        pass
