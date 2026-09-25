# core/formatting.py
def format_custom_number(val, decimals=2):
    """
    Formatea números separando millares con apóstrofe (')
    y decimales con punto (.).
    Ejemplos:
      100.0       -> "100.00"
      1000.0      -> "1'000.00"
      1000000.5   -> "1'000'000.50"
    """
    if val is None:
        return f"0.{'0' * decimals}"
    try:
        amount = float(val)
    except (TypeError, ValueError):
        amount = 0.0
    # Formatea primero con comas estándar
    formatted = f"{amount:,.{decimals}f}"
    # Reemplaza la coma de millares por el apóstrofe
    return formatted.replace(",", "'")


def format_money(value, currency="CUP"):
    """Formatea importes con dos decimales y apostrofe como separador de miles."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    formatted = format_custom_number(amount)
    return f"{formatted} {currency}"


def format_money_usd(value):
    """Formatea importes específicamente en USD para módulos de logística y compras."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    return format_custom_number(amount)  # Solo devuelve el número formateado sin sufijo de moneda