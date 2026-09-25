# database/connection.py
import sqlite3
import sys
from pathlib import Path

def get_base_dir():
    """Obtiene el directorio base del proyecto (desarrollo o empaquetado)."""
    try:
        # Si está empaquetado con PyInstaller
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        else:
            return Path(__file__).resolve().parent.parent
    except Exception:
        return Path(__file__).resolve().parent.parent

# Definir la ruta de la base de datos en la raíz del proyecto
BASE_DIR = get_base_dir()
DB_PATH = BASE_DIR / "inventario.ilp"

def get_connection():
    """Establece y retorna la conexión a la base de datos SQLite con configuración anti-apagones."""
    # Asegurar que el directorio de la base de datos existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    # Activar la validación de llaves foráneas en SQLite
    conn.execute("PRAGMA foreign_keys = 1")
    # Activar modo WAL (Write-Ahead Logging) para mejor persistencia ante apagones
    conn.execute("PRAGMA journal_mode=WAL")
    # Configurar synchronous=NORMAL para balance entre rendimiento y seguridad
    conn.execute("PRAGMA synchronous=NORMAL")
    # Configurar para que las filas se comporten como diccionarios (acceso por nombre de columna)
    conn.row_factory = sqlite3.Row 
    return conn