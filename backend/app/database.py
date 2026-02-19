# database.py — SQLAlchemy motor ve oturum yönetimi
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    """Tüm modellerin temel sınıfı."""
    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.APP_DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: veritabanı oturumu sağlar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Tüm tabloları oluşturur ve eksik sütunları ekler."""
    import app.models  # noqa: F401 — modelleri yükle
    Base.metadata.create_all(bind=engine)
    _migrate_accounts_table()
    _migrate_locations_table()


def _migrate_accounts_table():
    """Account tablosuna yeni sütunları ekler (SQLite ALTER TABLE)."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)

    if "accounts" not in insp.get_table_names():
        return

    existing_cols = {c["name"] for c in insp.get_columns("accounts")}

    migrations = [
        ("account_status", "VARCHAR(50) DEFAULT 'active'"),
        ("appeal_status", "VARCHAR(50) DEFAULT 'none'"),
        ("status_message", "TEXT"),
        ("last_checked_at", "DATETIME"),
        ("last_appeal_at", "DATETIME"),
        # Web otomasyon alanları
        ("password_encrypted", "TEXT"),
        ("email_encrypted", "TEXT"),
        ("email_password_encrypted", "TEXT"),
        ("session_cookies", "TEXT"),
        ("session_valid", "BOOLEAN DEFAULT 0"),
        ("last_login_at", "DATETIME"),
        ("two_factor_seed", "VARCHAR(100)"),
        ("login_method", "VARCHAR(50) DEFAULT 'password'"),
    ]

    with engine.begin() as conn:
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                conn.execute(text(
                    f"ALTER TABLE accounts ADD COLUMN {col_name} {col_type}"
                ))


def _migrate_locations_table():
    """Locations tablosuna list_name sütununu ekler."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)

    if "locations" not in insp.get_table_names():
        return

    existing_cols = {c["name"] for c in insp.get_columns("locations")}

    if "list_name" not in existing_cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE locations ADD COLUMN list_name VARCHAR(200) DEFAULT 'Genel' NOT NULL"
            ))
