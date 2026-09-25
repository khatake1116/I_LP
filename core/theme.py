# core/theme.py
"""
Sistema centralizado de temas para la aplicación.

Responsabilidades:
- Validar el tema solicitado.
- Cargar el QSS principal.
- Cargar los componentes QSS.
- Aplicar el tema a QApplication.
- Mantener compatibilidad con desarrollo y PyInstaller.
"""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.paths import get_styles_path


# Temas soportados por la aplicación.
SUPPORTED_THEMES = {"dark", "light"}

# Orden fijo de carga de componentes.
# El tema base se carga primero y los componentes después.
COMPONENT_FILES = (
    "buttons.qss",
    "tables.qss",
    "dialogs.qss",
    "tabs.qss",
    "dashboard.qss",
)


def normalize_theme(theme: str) -> str:
    """
    Normaliza y valida el nombre del tema.

    Si el tema recibido no es válido, utiliza dark como fallback.
    """
    if not isinstance(theme, str):
        return "dark"

    theme = theme.strip().lower()

    if theme not in SUPPORTED_THEMES:
        return "dark"

    return theme


def load_qss_file(file_path: Path) -> str:
    """
    Lee un archivo QSS UTF-8.

    Devuelve una cadena vacía si no puede leerse.
    """
    if not file_path.exists() or not file_path.is_file():
        return ""

    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def load_theme_qss(theme: str = "dark") -> str:
    """
    Construye el QSS completo del tema.

    Estructura:

        ui/styles/
        ├── dark.qss
        ├── light.qss
        └── components/
            ├── buttons.qss
            ├── tables.qss
            ├── dialogs.qss
            ├── tabs.qss
            └── dashboard.qss

    El tema base se carga primero.
    Los componentes se concatenan posteriormente.
    
    NOTA: El tema oscuro ya incluye todos los estilos necesarios,
    por lo que no carga componentes externos para evitar sobrescrituras.
    """

    theme = normalize_theme(theme)

    styles_dir = get_styles_path()
    theme_file = styles_dir / f"{theme}.qss"

    base_qss = load_qss_file(theme_file)

    if not base_qss:
        return ""

    # El tema oscuro ya tiene todos los estilos definidos en el archivo base
    # Los componentes tienen colores hardcodeados del tema claro
    if theme == "dark":
        return base_qss

    # Solo cargar componentes para el tema claro
    components_dir = styles_dir / "components"

    qss_parts = [base_qss]

    for component_name in COMPONENT_FILES:
        component_file = components_dir / component_name
        component_qss = load_qss_file(component_file)

        if component_qss:
            qss_parts.append(component_qss)

    return "\n\n".join(qss_parts)


def apply_theme(app: QApplication, theme: str = "dark") -> bool:
    """
    Carga y aplica un tema a QApplication.

    Devuelve:
        True  -> tema aplicado correctamente.
        False -> no se pudo cargar el QSS.
    """

    theme = normalize_theme(theme)
    qss = load_theme_qss(theme)

    if not qss:
        return False

    app.setStyleSheet(qss)
    app.setProperty("currentTheme", theme)

    return True


def get_current_theme(app: QApplication) -> str:
    """
    Devuelve el tema actualmente aplicado.

    Si no existe información del tema, devuelve dark.
    """
    theme = app.property("currentTheme")

    if isinstance(theme, str) and theme in SUPPORTED_THEMES:
        return theme

    return "dark"


def get_theme_file(theme: str) -> Path:
    """
    Devuelve la ruta absoluta del archivo QSS principal.
    """
    theme = normalize_theme(theme)
    return get_styles_path() / f"{theme}.qss"