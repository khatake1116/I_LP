# core/paths.py
"""
Utilidades centralizadas para rutas de la aplicación.

Responsabilidades:
- Resolver recursos incluidos con la aplicación.
- Resolver directorios persistentes.
- Resolver assets, iconos y estilos.
- Leer y guardar configuración.
- Detectar ejecución normal o empaquetada con PyInstaller.

La lógica de carga/aplicación de temas pertenece a core/theme.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "dark",
    "db_setup_prompt_done": False,
}


# ==========================================================
# DETECCIÓN DE ENTORNO
# ==========================================================

def is_frozen() -> bool:
    """
    Devuelve True cuando la aplicación está ejecutándose
    como un ejecutable empaquetado, por ejemplo con PyInstaller.
    """
    return getattr(sys, "frozen", False)


# ==========================================================
# DIRECTORIO BASE DEL PROYECTO
# ==========================================================

def get_base_dir() -> Path:
    """
    Obtiene el directorio base de la aplicación.

    Desarrollo:
        directorio raíz del proyecto.

    PyInstaller:
        directorio donde se encuentra el ejecutable.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


# ==========================================================
# RECURSOS DE LA APLICACIÓN
# ==========================================================

def get_resource_path(relative_path: str | Path) -> Path:
    """
    Obtiene la ruta absoluta de un recurso incluido en la aplicación.

    En desarrollo:
        proyecto/<relative_path>

    En PyInstaller:
        _MEIPASS/<relative_path>

    Esta función debe utilizarse para recursos de solo lectura,
    como:
        - QSS
        - iconos
        - imágenes
        - assets
    """
    relative = Path(relative_path)

    if is_frozen():
        # PyInstaller utiliza _MEIPASS para los recursos incluidos.
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            return Path(meipass) / relative

    return get_base_dir() / relative


# ==========================================================
# RECURSOS DE UI
# ==========================================================

def get_ui_path() -> Path:
    """Obtiene el directorio principal de recursos de UI."""
    return get_resource_path("ui")


def get_ui_assets_path(filename: str) -> Path:
    """Obtiene la ruta de un archivo dentro de ui/assets/."""
    return get_resource_path(Path("ui") / "assets" / filename)


def get_ui_icons_path(filename: str) -> Path:
    """Obtiene la ruta de un icono dentro de ui/assets/icons/."""
    return get_resource_path(
        Path("ui") / "assets" / "icons" / filename
    )


# ==========================================================
# ESTILOS
# ==========================================================

def get_styles_path() -> Path:
    """
    Obtiene el directorio principal de estilos.

    Estructura esperada:

        ui/
        └── styles/
            ├── dark.qss
            ├── light.qss
            └── components/
                ├── buttons.qss
                ├── tables.qss
                ├── dialogs.qss
                ├── tabs.qss
                └── dashboard.qss
    """
    return get_resource_path(Path("ui") / "styles")


def get_theme_path(theme: str) -> Path:
    """
    Obtiene la ruta del archivo QSS correspondiente al tema.

    Args:
        theme:
            "dark" o "light"
    """
    theme = theme.lower().strip()

    if theme not in {"dark", "light"}:
        theme = "dark"

    return get_styles_path() / f"{theme}.qss"


def get_components_path() -> Path:
    """Obtiene el directorio donde se encuentran los componentes QSS."""
    return get_styles_path() / "components"


# ==========================================================
# BASE DE DATOS
# ==========================================================

def get_database_path() -> Path:
    """
    Obtiene el directorio persistente de la base de datos.

    La base de datos NO se considera un recurso temporal de
    PyInstaller, por lo que se utiliza get_base_dir().
    """
    return get_base_dir() / "database"


# ==========================================================
# CONFIGURACIÓN PERSISTENTE
# ==========================================================

def get_config_path() -> Path:
    """
    Obtiene la ruta del archivo de configuración persistente.

    Ejemplo:
        config.json
    """
    return get_base_dir() / "config.json"


def get_log_path() -> Path:
    """Obtiene la ruta del archivo de log persistente."""
    return get_base_dir() / "inventario.log"


# ==========================================================
# LECTURA DE CONFIGURACIÓN
# ==========================================================

def get_app_config() -> dict[str, Any]:
    """
    Lee la configuración persistente.

    Si el archivo no existe o está dañado, devuelve una
    configuración segura por defecto.
    """
    config_file = get_config_path()

    if not config_file.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with config_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return DEFAULT_CONFIG.copy()

        # Combinar defaults con configuración existente.
        config = DEFAULT_CONFIG.copy()
        config.update(data)

        return config

    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return DEFAULT_CONFIG.copy()


# ==========================================================
# GUARDADO DE CONFIGURACIÓN
# ==========================================================

def save_app_config(config: dict[str, Any]) -> bool:
    """
    Guarda la configuración persistente.

    Devuelve:
        True  -> guardado correctamente.
        False -> ocurrió un error.
    """
    config_file = get_config_path()

    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with config_file.open("w", encoding="utf-8") as file:
            json.dump(
                config,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return True

    except (OSError, TypeError, ValueError):
        return False


# ==========================================================
# CONFIGURACIÓN DEL TEMA
# ==========================================================

def get_saved_theme() -> str:
    """
    Obtiene el tema guardado.

    Solo devuelve:
        "dark"
        "light"
    """
    theme = get_app_config().get("theme", "dark")

    if not isinstance(theme, str):
        return "dark"

    theme = theme.lower().strip()

    return theme if theme in {"dark", "light"} else "dark"


def save_theme(theme: str) -> bool:
    """
    Guarda el tema seleccionado.

    Args:
        theme:
            "dark" o "light"
    """
    theme = theme.lower().strip()

    if theme not in {"dark", "light"}:
        return False

    config = get_app_config()
    config["theme"] = theme

    return save_app_config(config)


# ==========================================================
# CONFIGURACIÓN DEL ASISTENTE DE BASE DE DATOS
# ==========================================================

def should_skip_db_setup_prompt() -> bool:
    """
    Determina si debe mostrarse el diálogo inicial de base de datos.

    Se omite cuando:
    - Ya se completó anteriormente.
    - Ya existe una base de datos activa.
    """
    config = get_app_config()

    if config.get("db_setup_prompt_done"):
        return True

    try:
        from database.connection import DB_PATH

        if DB_PATH.exists():
            config["db_setup_prompt_done"] = True
            save_app_config(config)
            return True

    except (ImportError, AttributeError):
        pass

    return False


def mark_db_setup_prompt_done() -> None:
    """Marca la configuración inicial de la base de datos como completada."""
    config = get_app_config()
    config["db_setup_prompt_done"] = True
    save_app_config(config)