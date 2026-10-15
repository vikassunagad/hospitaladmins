"""SQLite + SQLAlchemy setup."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})


@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, _record):
    # Take manual control of transactions (see _on_begin) and enable constraints.
    dbapi_conn.isolation_level = None
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=15000")
    cur.close()


@event.listens_for(engine, "begin")
def _on_begin(conn):
    # BEGIN IMMEDIATE = take the write lock at the start of every transaction.
    # Two simultaneous reservations therefore run one after the other, never together.
    conn.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
