"""Script para inicializar la base de datos.

Crea todas las tablas definidas en los modelos.
"""

import sys
import os

# Añadir el directorio app al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.db import init_db, engine
from app.core.config import get_settings


def main():
    settings = get_settings()
    print(f"Inicializando base de datos...")
    print(f"  URL: {settings.database_url}")

    init_db()

    # Verificar
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"  Tablas creadas: {tables}")
    print(f"  ✓ Base de datos lista.")


if __name__ == "__main__":
    main()

