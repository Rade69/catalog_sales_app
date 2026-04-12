from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.utils.paths import get_db_path


def get_encrypted_db_url(password: Optional[str] = None) -> str:
    """Vrati URL za enkriptovanu ili neenkriptovanu bazu."""
    DB_PATH = get_db_path()
    
    if password:
        # SQLCipher URL format: sqlite+pysqlcipher://:password@/path/to/db
        return f"sqlite+pysqlcipher://:{password}@{DB_PATH}?cipher=aes-256-cfb&kdf_iter=64000"
    else:
        return f"sqlite:///{DB_PATH}"


def create_encrypted_engine(password: Optional[str] = None):
    """Kreira SQLAlchemy engine sa SQLCipher podrškom."""
    DATABASE_URL = get_encrypted_db_url(password)
    
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
    
    return engine


# Globalni engine (inicijalizuje se pri pokretanju aplikacije)
engine = None
SessionLocal = None


def init_db(password: Optional[str] = None) -> None:
    """Inicijalizuje bazu podataka sa opcionom enkripcijom."""
    global engine, SessionLocal
    
    engine = create_encrypted_engine(password)
    
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )


@contextmanager
def session_scope():
    """Context manager za sigurno upravljanje sesijama."""
    if SessionLocal is None:
        raise RuntimeError("Baza nije inicijalizovana. Pozovite init_db() pre upotrebe.")
    
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


def run_migrations(password: Optional[str] = None) -> None:
    """
    Pokreće Alembic migracije na startup aplikacije.
    
    Ovo osigurava da je baza podataka ažurirana prije nego što
    aplikacija počne sa radom.
    """
    from alembic.config import Config
    from alembic import command
    from pathlib import Path as SysPath
    
    # Get the project root directory (parent of app/)
    project_root = SysPath(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    
    # Postavi URL baze u alembic konfiguraciju
    alembic_cfg.set_main_option("sqlalchemy.url", get_encrypted_db_url(password))
    
    # Run upgrade head
    command.upgrade(alembic_cfg, "head")


def is_database_encrypted() -> bool:
    """
    Proveri da li je baza već enkriptovana.
    
    Pokušava da otvori bazu bez lozinke. Ako uspe, baza nije enkriptovana.
    Ako ne uspe sa "file is encrypted or is not a database", onda je enkriptovana.
    """
    import sqlite3
    
    db_path = get_db_path()
    if not db_path.exists():
        return False
    
    try:
        # Pokušaj da otvoriš bazu bez lozinke
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1")
        conn.close()
        return False
    except sqlite3.DatabaseError as e:
        if "file is encrypted or is not a database" in str(e):
            return True
        # Druge greške - pretpostavi da nije enkriptovana
        return False
    except Exception:
        return False


def migrate_plain_to_encrypted(password: str) -> bool:
    """
    Migrira plain SQLite bazu u SQLCipher enkriptovanu.
    
    Ovo koristi sqlcipher CLI tool koji mora biti instaliran.
    """
    import subprocess
    import shutil
    import tempfile
    
    db_path = get_db_path()
    if not db_path.exists():
        return True  # Nema baze za migraciju
    
    backup_path = db_path.with_suffix('.db.backup')
    
    try:
        # 1. Napravi backup
        shutil.copy2(db_path, backup_path)
        
        # 2. Koristi sqlcipher CLI za migraciju
        # Prvo export podataka iz plain baze
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            export_file = f.name
        
        # Export SQL dump
        export_cmd = f'sqlite3 {db_path} ".dump" > {export_file}'
        result = subprocess.run(export_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Export failed: {result.stderr}")
        
        # 3. Kreiraj novu enkriptovanu bazu
        temp_encrypted = db_path.with_suffix('.db.encrypted')
        
        # Kreiraj praznu enkriptovanu bazu
        create_cmd = f'sqlcipher {temp_encrypted} "PRAGMA key = \'{password}\';" ".exit"'
        result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Create encrypted DB failed: {result.stderr}")
        
        # 4. Import podataka u enkriptovanu bazu
        import_cmd = f'sqlcipher {temp_encrypted} "PRAGMA key = \'{password}\';" ".read {export_file}"'
        result = subprocess.run(import_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Import failed: {result.stderr}")
        
        # 5. Zameni originalnu bazu
        old_db = db_path.with_suffix('.db.old')
        if old_db.exists():
            old_db.unlink()
        
        db_path.rename(old_db)
        temp_encrypted.rename(db_path)
        
        # 6. Očisti privremene fajlove
        import os
        os.unlink(export_file)
        
        return True
        
    except Exception as e:
        # Restore backup ako migracija ne uspe
        if backup_path.exists() and db_path.exists():
            try:
                db_path.unlink()
                backup_path.rename(db_path)
            except:
                pass
        
        raise Exception(f"Migracija nije uspela: {e}")


# Inicijalizuj bazu bez enkripcije za kompatibilnost
# Ovo će biti promenjeno kada se doda autentikacija
DB_PATH = get_db_path()
engine = create_encrypted_engine(None)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)