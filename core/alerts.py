# core/alerts.py
from database.connection import get_connection

def obtener_alertas_retrasos(dias_limite=15):
    """
    Detecta compras que no han sido recibidas y superan el límite de días en tránsito.
    Retorna una lista de diccionarios con los detalles de la alerta.
    """
    query = """
        SELECT 
            c.id AS compra_id,
            c.articulo_id,
            a.nombre,
            c.fecha AS fecha_compra,
            c.cantidad,
            CAST((julianday('now') - julianday(c.fecha)) AS INTEGER) AS dias_transcurridos
        FROM compras c
        JOIN articulos a ON c.articulo_id = a.id
        WHERE c.recibido = 0 AND dias_transcurridos >= ?
        ORDER BY dias_transcurridos DESC
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Pasamos el parámetro dias_limite de forma segura
    cursor.execute(query, (dias_limite,))
    rows = cursor.fetchall()
    conn.close()
    
    # Convertimos los resultados a diccionarios para que PySide6 los consuma fácilmente
    alertas = [dict(row) for row in rows]
    return alertas