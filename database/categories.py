# database/categories.py
# Funciones CRUD para gestión de categorías en ILP
import sqlite3
import logging
from database.connection import get_connection
from core.undo_redo import AuditLogger

logger = logging.getLogger(__name__)

# Categorías por defecto del sistema
CATEGORIAS_POR_DEFECTO = [
    "General",
    "Electrónica",
    "Ropa",
    "Hogar",
    "Herramientas",
    "Calzado",
    "Deportes",
    "Juguetes",
    "Libros",
    "Salud",
    "Belleza",
    "Alimentos",
    "Automotriz",
    "Oficina",
    "Tecnología"
]

def get_categorias():
    """Retorna todas las categorías únicas válidas de la base de datos."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener categorías únicas ignorando nulos, vacíos y artículos temporales
        cursor.execute("""
            SELECT DISTINCT categoria 
            FROM articulos 
            WHERE categoria IS NOT NULL 
              AND TRIM(categoria) != ''
              AND nombre NOT LIKE '\\_CATEGORIA\\_%' ESCAPE '\\'
            ORDER BY categoria
        """)
        
        rows = cursor.fetchall()
        categorias_db = [row['categoria'] for row in rows]
        
        # Si no hay categorías en la base de datos, retornar las por defecto
        if not categorias_db:
            return CATEGORIAS_POR_DEFECTO.copy()
        
        return categorias_db
    except Exception as e:
        logger.error(f"Error al obtener categorías: {e}")
        return CATEGORIAS_POR_DEFECTO.copy()
    finally:
        if conn:
            conn.close()

def crear_categoria(nombre):
    """Crea una nueva categoría (como artículo placeholder temporal en la DB)."""
    if not nombre or not nombre.strip():
        return False, "El nombre de la categoría no puede estar vacío"
    
    nombre = nombre.strip()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la categoría ya existe
        cursor.execute("SELECT COUNT(*) as count FROM articulos WHERE categoria = ?", (nombre,))
        count = cursor.fetchone()['count']
        
        if count > 0:
            return False, "La categoría ya existe"
        
        # Insertar un artículo "placeholder" con la nueva categoría
        cursor.execute("""
            INSERT INTO articulos (nombre, categoria, peso_lb)
            VALUES (?, ?, ?)
        """, (f"_CATEGORIA_{nombre}", nombre, 0.0))
        
        conn.commit()
        nuevo_id = cursor.lastrowid
        
        # Registrar en audit trail
        AuditLogger.log_change(
            tabla="articulos",
            registro_id=nuevo_id,
            accion="INSERT_CATEGORIA",
            valor_nuevo=f"Categoría: {nombre}",
            campo="categoria"
        )
        
        logger.info(f"Categoría creada: {nombre}")
        return True, "Categoría creada exitosamente"
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error al crear categoría: {e}")
        return False, f"Error al crear categoría: {e}"
    finally:
        if conn:
            conn.close()

def actualizar_categoria(nombre_anterior, nombre_nuevo):
    """Actualiza el nombre de una categoría en todos los artículos que la usan."""
    if not nombre_nuevo or not nombre_nuevo.strip():
        return False, "El nuevo nombre de categoría no es válido"

    nombre_anterior = nombre_anterior.strip()
    nombre_nuevo = nombre_nuevo.strip()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que la categoría anterior existe
        cursor.execute("SELECT COUNT(*) as count FROM articulos WHERE categoria = ?", (nombre_anterior,))
        count = cursor.fetchone()['count']
        
        if count == 0:
            return False, "La categoría anterior no existe"
        
        # Verificar que la nueva categoría no exista (si es un nombre diferente)
        if nombre_anterior != nombre_nuevo:
            cursor.execute("SELECT COUNT(*) as count FROM articulos WHERE categoria = ?", (nombre_nuevo,))
            count_nuevo = cursor.fetchone()['count']
            if count_nuevo > 0:
                return False, "La nueva categoría ya existe"
        
        # Actualizar todos los artículos con la categoría anterior
        cursor.execute("""
            UPDATE articulos 
            SET categoria = ? 
            WHERE categoria = ?
        """, (nombre_nuevo, nombre_anterior))
        
        conn.commit()
        affected_rows = cursor.rowcount
        
        # Registrar en audit trail
        AuditLogger.log_change(
            tabla="articulos",
            registro_id=0,  # Afecta múltiples registros
            accion="UPDATE_CATEGORIA",
            valor_anterior=f"Categoría: {nombre_anterior}",
            valor_nuevo=f"Categoría: {nombre_nuevo}",
            campo="categoria",
            metadata={"affected_rows": affected_rows}
        )
        
        logger.info(f"Categoría actualizada: {nombre_anterior} → {nombre_nuevo} ({affected_rows} artículos afectados)")
        return True, f"Categoría actualizada en {affected_rows} artículos"
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error al actualizar categoría: {e}")
        return False, f"Error al actualizar categoría: {e}"
    finally:
        if conn:
            conn.close()

def eliminar_categoria(nombre):
    """Elimina una categoría reasignando sus artículos a 'General'."""
    if not nombre:
        return False, "Nombre de categoría no válido"
        
    nombre = nombre.strip()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que la categoría existe
        cursor.execute("SELECT COUNT(*) as count FROM articulos WHERE categoria = ?", (nombre,))
        count = cursor.fetchone()['count']
        
        if count == 0:
            return False, "La categoría no existe"
        
        # Actualizar artículos con la categoría a 'General'
        cursor.execute("""
            UPDATE articulos 
            SET categoria = 'General' 
            WHERE categoria = ?
        """, (nombre,))
        
        conn.commit()
        affected_rows = cursor.rowcount
        
        # Registrar en audit trail
        AuditLogger.log_change(
            tabla="articulos",
            registro_id=0,
            accion="DELETE_CATEGORIA",
            valor_anterior=f"Categoría: {nombre}",
            valor_nuevo="Categoría: General",
            campo="categoria",
            metadata={"affected_rows": affected_rows}
        )
        
        logger.info(f"Categoría eliminada: {nombre} ({affected_rows} artículos actualizados a 'General')")
        return True, f"Categoría eliminada. {affected_rows} artículos actualizados a 'General'"
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error al eliminar categoría: {e}")
        return False, f"Error al eliminar categoría: {e}"
    finally:
        if conn:
            conn.close()

def limpiar_categorias_temporales():
    """Elimina los artículos placeholder creados exclusivamente para definir categorías."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Eliminar artículos que empiezan con "_CATEGORIA_"
        cursor.execute("""
            DELETE FROM articulos 
            WHERE nombre LIKE '_CATEGORIA_%'
        """)
        
        conn.commit()
        deleted_count = cursor.rowcount
        
        logger.info(f"Artículos temporales de categorías eliminados: {deleted_count}")
        return deleted_count
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error al limpiar categorías temporales: {e}")
        return 0
    finally:
        if conn:
            conn.close()