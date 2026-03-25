from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.utils.paths import get_db_path


DB_PATH = get_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Postavi SQLite WAL mode za bolje performanse."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,   # ORM objekti ostaju čitljivi van sesije
)


def init_db() -> None:
    """
    Inicijalizuje bazu podataka koristeći Alembic migracije.
    
    NAPOMENA: Ova funkcija je zadržana za kompatibilnost, ali se ne preporučuje
    za direktno pozivanje. Umjesto nje, koristite alembic upgrade head
    u run.py prije pokretanja aplikacije.
    """
    # Napomena: Base.metadata.create_all() se više ne koristi za produkciju
    # Koristite alembic upgrade head umjesto ovoga
    pass


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        if session.is_active:
            session.rollback()
        raise
    finally:
        session.close()


def run_migrations() -> None:
    """
    Pokreće Alembic migracije na startup aplikacije.
    
    Ovo osigurava da je baza podataka ažurirana prije nego što
    aplikacija počne sa radom.
    """
    from alembic.config import Config
    from alembic import command
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from pathlib import Path as SysPath
    
    # Get the project root directory (parent of app/)
    project_root = SysPath(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    
    # Run upgrade head
    command.upgrade(alembic_cfg, "head")
