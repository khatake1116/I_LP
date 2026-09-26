# scripts/generate_dark_components.py
"""
Genera ui/styles/components/dark/<nombre>.qss a partir de los componentes
del tema claro, aplicando el mapeo de paleta Catppuccin (tema oscuro).

Motivo: core/theme.py antes omitía los componentes en modo oscuro, lo que
provocaba una interfaz "comprimida/forzada" (sin paddings, alturas mínimas,
radios ni tipografía definida). Ahora ambos temas cargan los mismos
componentes; esta herramienta mantiene la versión oscura sincronizada.

Uso:
    python scripts/generate_dark_components.py

Idempotente: puede ejecutarse tantas veces como se modifiquen los .qss
del tema claro.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
COMPONENTS_DIR = BASE_DIR / "ui" / "styles" / "components"
DARK_DIR = COMPONENTS_DIR / "dark"

# Mapeo exacto de colores del tema claro -> tema oscuro (Catppuccin).
# Basado en la identidad declarada en ui/styles/dark.qss.
COLOR_MAP = {
    # Superficies base
    "#FFFFFF": "#1E1E2E",
    "#F5F5F5": "#181825",
    "#F5F7F9": "#181825",
    "#F8FAFC": "#181825",
    "#F7FAFC": "#181825",
    "#F2F6F8": "#1E1E2E",
    "#ECF0F1": "#1E1E2E",
    # Bordes y divisores
    "#CBD5E1": "#313244",
    "#C7D5DF": "#313244",
    "#BDC3C7": "#313244",
    "#D5DBDB": "#313244",
    "#E1E7EC": "#313244",
    "#AFC4D4": "#45475A",
    # Scrollbars
    "#F1F5F8": "#181825",
    "#B8C4CE": "#45475A",
    # Azules de texto/acento
    "#1F2D3D": "#CDD6F4",
    "#2C3E50": "#CDD6F4",
    "#34495E": "#CDD6F4",
    "#5D6D7E": "#A6ADC8",
    "#1F5F8B": "#89B4FA",
    # Acento primario (botones/tabs/selecciones)
    "#3498DB": "#89B4FA",
    "#2980B9": "#B4BEFE",
    "#2471A3": "#7FA0E8",
    # Tono sobre acento: en oscuro el acento es claro, el texto debe ser oscuro
    "#7F8C8D": "#11111B",
    # Botón secundario
    "#95A5A6": "#45475A",
    # Variantes suaves de hover/selección sobre azul
    "#EAF2F8": "#1E1E2E",
    "#D9EAF8": "#2A2A40",
    "#C7DDF0": "#363650",
    "#EAF0F4": "#1E1E2E",
    "#DDE8EF": "#313244",
    "#D5E2EA": "#313244",
    # Estados deshabilitados
    "#AAB2B8": "#585B70",
    "#F2F4F5": "#181825",
    "#E1E5E8": "#313244",
    "#F4F6F7": "#181825",
    # Éxito
    "#247A3D": "#A6E3A1",
    # Badge de estado: en claro es verde medio con texto blanco;
    # en oscuro se mantiene el fondo verde y el texto blanco (verificado).
    "#2E9B65": "#2E9B65",
    "#F1F8F4": "#1E2E24",
    # Error
    "#A93226": "#F38BA8",
    "#C0392B": "#EBA0AC",
    "#E74C3C": "#F38BA8",
    "#FDEDEC": "#2A1E28",
    # Advertencia
    "#8A5A00": "#FAB387",
    "#FFF7E6": "#2A241B",
    "#F2D49B": "#585B70",
    # Total POS (dorado): en claro es dorado oscuro sobre fondo blanco;
    # en oscuro se usa el amarillo Catppuccin para mantener contraste.
    "#B7791F": "#F9E2AF",
}

HEADER = (
    "/* ==========================================================\n"
    "   ATENCION: archivo GENERADO automaticamente.\n"
    "   Fuente: ui/styles/components/{source}\n"
    "   Herramienta: scripts/generate_dark_components.py\n"
    "   No editar a mano: regenerar tras cambiar el componente claro.\n"
    "   ========================================================== */\n\n"
)


def to_dark(text: str) -> str:
    """Aplica el mapeo de paleta clara -> oscura (insensible a mayusculas).

    Se sustituyen los hex sobre una copia en minusculas para preservar
    intactas las propiedades QSS (nombres, unidades y cadenas), que son
    sensibles a mayusculas.
    """
    lowered = text.lower()
    for light_hex, dark_hex in COLOR_MAP.items():
        lowered = lowered.replace(light_hex.lower(), dark_hex.lower())
    return lowered


def main() -> None:
    DARK_DIR.mkdir(parents=True, exist_ok=True)

    generated = []
    for qss_file in sorted(COMPONENTS_DIR.glob("*.qss")):
        content = qss_file.read_text(encoding="utf-8")
        dark_content = HEADER.format(source=qss_file.name) + to_dark(content)
        out_path = DARK_DIR / qss_file.name
        out_path.write_text(dark_content, encoding="utf-8")
        generated.append(out_path.relative_to(BASE_DIR))

    print(f"Componentes oscuros generados en {DARK_DIR}:")
    for path in generated:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
