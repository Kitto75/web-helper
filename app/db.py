from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///panel.db', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(admins)").fetchall()]
        if "allowed_inbounds" not in cols:
            conn.exec_driver_sql("ALTER TABLE admins ADD COLUMN allowed_inbounds TEXT DEFAULT ''")
        user_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
        if "admin_comment" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN admin_comment TEXT DEFAULT ''")
