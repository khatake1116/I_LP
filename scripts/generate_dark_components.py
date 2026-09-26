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

import re
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
    # Botón secundario: superficie neutra elevada (Surface1). El texto
    # blanco sobre #45475A mantiene el mismo contraste que el claro
    # (blanco sobre #95A5A6). Antes se mapeaba a #11111B (crash), lo que
    # dejaba bordes invisibles y rompía la identidad del tema oscuro.
    "#95A5A6": "#45475A",
    "#7F8C8D": "#585B70",
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
    # Peligro: fondo rojo. En claro (#E74C3C) lleva texto blanco; en
    # oscuro no puede usarse un rosa pastel con texto blanco (baja
    # contraste), por eso btn_danger fija su propio color de texto.
    "#E74C3C": "#E74C3C",
    "#FDEDEC": "#2A1E28",
    # Advertencia
    "#8A5A00": "#FAB387",
    "#FFF7E6": "#2A241B",
    "#F2D49B": "#585B70",
    # Total POS (dorado): en claro es dorado oscuro sobre fondo blanco;
    # en oscuro se usa el amarillo Catppuccin para mantener contraste.
    "#B7791F": "#F9E2AF",
}

# Reglas especiales de cuerpo de regla (aplicadas ANTES del mapeo
# genérico de COLOR_MAP, mediante expresiones regulares):
#
# Cuando el texto claro es BLANCO sobre un relleno de tono medio
# (#95A5A6 secundario, #E74C3C peligro), al mapear el fondo a una
# superficie oscura Catppuccin (Surface1/Osuroy) ese blanco ya no es
# legible y debe sustituirse por la tinta clara del tema (#CDD6F4).
# El patrón reconoce tanto el hex claro original como su equivalente
# oscuro ya mapeado, por robustez.
SPECIAL_BODY_RULES = {
    r"(background-color:\s*#(?:95A5A6|45475A);\s*"
    r"[^{}]*?color:\s*)#FFFFFF":
        r"\g<1>#CDD6F4",
    r"(background-color:\s*#(?:E74C3C|F38BA8);\s*"
    r"[^{}]*?color:\s*)#FFFFFF":
        r"\g<1>#CDD6F4",
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

    IMPORTANTE: solo se reemplazan los hex dentro del cuerpo { ... } de
    cada regla. Los selectores QSS son sensibles a mayusculas en Qt6
    (QTypeSelector y los objectName como "PosPrimaryButton"), por lo que
    minusculizar el archivo completo dejaba TODOS los componentes oscuros
    inoperantes: la interfaz caia al estilo por defecto de Qt y se veia
    distinta (apretada/forzada) respecto al tema claro. Las cadenas de
    texto (font-family, url()) tampoco deben alterarse.
    """

    def _map_body(match):
        body = match.group(1)

        # 1) Casos especiales (patrones multi-linea que dependen del
        #    valor YA mapeado de background-color). Se aplican antes que
        #    el reemplazo generico de "#FFFFFF".
        for pattern, replacement in SPECIAL_BODY_RULES.items():
            body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)

        # 2) Resto de la paleta.
        for light_hex, dark_hex in COLOR_MAP.items():
            body = re.sub(re.escape(light_hex), dark_hex, body, flags=re.IGNORECASE)
        return "{" + body + "}"

    return re.sub(r"\{([^{}]*)\}", _map_body, text)


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
