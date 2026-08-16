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
    # Importar todos los modelos para que SQLAlchemy los registre.
    # Fase 1: solo research existe. Los demás módulos se importan en su try/except
    # para que esta función no rompa cuando aún no estén implementados.

    # Módulo portfolio (Fase 2)
    try:
        from app.modules.portfolio.models import Position, Transaction, Account  # noqa: F401
    except ImportError:
        pass

    # Módulo screener (Fase 3)
    try:
        from app.modules.screener.models import ScreenerResult  # noqa: F401
    except ImportError:
        pass

    # Módulo alerts (Fase 4)
    try:
        from app.modules.alerts.models import Alert  # noqa: F401
    except ImportError:
        pass

    # Módulo earnings (Fase 5)
    try:
        from app.modules.earnings.models import EarningsAnalysis  # noqa: F401
    except ImportError:
        pass

    # Módulo copilot (Fase 6)
    try:
        from app.modules.copilot.models import ChatMessage  # noqa: F401
    except ImportError:
        pass

    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency de FastAPI para obtener una sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
