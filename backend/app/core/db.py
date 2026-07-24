"""SQLAlchemy database setup."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite necesita connect_args especiales; Postgres no
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos."""

    pass


def init_db() -> None:
    """Crea todas las tablas. Llamar al arrancar."""
    # Importar todos los modelos para que SQLAlchemy los registre
    from app.modules.portfolio.models import Position, Transaction, Account  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency de FastAPI para obtener una sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

