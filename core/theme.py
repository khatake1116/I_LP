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
            ├── buttons.qss      (geometría + colores del tema claro)
            ├── tables.qss
            ├── dialogs.qss
            ├── tabs.qss
            ├── dashboard.qss
            └── dark/            (versión oscura generada de cada
                                  componente; ver
                                  scripts/generate_dark_components.py)

    El tema base se carga primero y los componentes después, por lo
    que estos aportan geometría (paddings, alturas mínimas, radios,
    tipografía) e identidad de color.

    IMPORTANTE: ambos temas deben cargar componentes. Si solo el tema
    claro los carga, el oscuro queda sin espaciados ni tamaños mínimos
    y la interfaz se ve comprimida y forzada respecto al claro.
    """

    theme = normalize_theme(theme)

    styles_dir = get_styles_path()
    theme_file = styles_dir / f"{theme}.qss"

    base_qss = load_qss_file(theme_file)

    if not base_qss:
        return ""

    components_dir = styles_dir / "components"

    # En el tema oscuro se cargan las variantes oscuras de los
    # componentes (misma geometría, paleta Catppuccin), para no
    # sobrescribir los colores del tema con los del claro.
    if theme == "dark":
        dark_components_dir = components_dir / "dark"
        if dark_components_dir.is_dir():
            components_dir = dark_components_dir

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