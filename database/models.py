# database/models.py
import sqlite3
import logging
import re
from datetime import date
from database.connection import get_connection
from core.constants import PurchaseStatus, ShipmentStatus, InventoryMovementType
from core.paths import get_log_path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(get_log_path()),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _sql_values(values):
    """Devuelve una lista SQL con comillas para usarse dentro de un IN (...)"""
    return ", ".join(f"'{value}'" for value in values)


def normalize_decimal(value):
    """Normaliza números decimales aceptando coma, punto y sufijos como lb."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return float(value)

    text = value.strip()
    if not text:
        return 0.0

    text = text.replace('lb', '').replace('LB', '').replace('lbs', '').replace('LBS', '').strip()
    text = text.replace(' ', '')

    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')

    text = re.sub(r'[^0-9.\-]', '', text)
    if not text or text in {'-', '.', '-.'}:
        return 0.0
    return float(text)


def print_formula_validation_report():
    """Imprime un reporte de validación de fórmulas para auditoría del módulo financiero."""
    print("\n=== Reporte de Validación de Fórmulas ===")
    print("1. Precio Ponderado (P_pond):")
    print("   Fórmula de costo medio ponderado aplicada en get_inventory_summary:")
    print("   P_pond = ((Stock Actual × P_actual) + (Cant. Nueva × P_nuevo)) / (Stock Actual + Cant. Nueva)")
    print("   Implementación actual: SUM(cantidad_recibida * precio_unitario) / SUM(cantidad_recibida)")
    print("   Esta expresión reproduce el promedio ponderado del costo por artículo, ajustando la base histórica de compras recibidas.")
    print("2. Pesaje Ponderado:")
    print("   El peso promedio de un artículo se deriva del campo a.peso_lb del catálogo y se multiplica por la cantidad por envío o compra.")
    print("   Formula de consolidacion: Peso Total = SUM(Cantidad_i * Peso Unidad_i)")
    print("   En la vista de logística, se muestra como valor numérico puro (ej. 21.00) sin concatenar 'lb' a la celda.")
    print("========================================\n")


def init_db():
    """Inicializa la base de datos creando las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Artículos (Catálogo base sin precio ponderado estático)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            categoria TEXT DEFAULT 'General',
            descripcion TEXT DEFAULT '',
            peso_lb REAL DEFAULT 0.0
        )
    """)

    # 2. Tabla Compras (Registro de entradas / Checkpoints)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            articulo_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            precio_unitario REAL NOT NULL DEFAULT 0.0,
            recibido BOOLEAN NOT NULL DEFAULT 0,
            fecha_recibido DATE,
            FOREIGN KEY (articulo_id) REFERENCES articulos (id) ON DELETE CASCADE
        )
    """)

    # 3. Tabla Destinatarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS destinatarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            direccion TEXT,
            numero TEXT,
            telefono TEXT,
            email TEXT,
            notas TEXT,
            activo BOOLEAN NOT NULL DEFAULT 1,
            fecha_registro DATE DEFAULT CURRENT_DATE
        )
    """)

    # 4. Tabla Envíos (Registro de salidas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            articulo_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            destinatario TEXT,
            metodo_envio TEXT,
            costo_lb REAL DEFAULT 0.0,
            modalidad_cobro TEXT NOT NULL DEFAULT 'Peso',
            peso_cobrado REAL DEFAULT 0.0,
            largo_cm REAL DEFAULT 0.0,
            ancho_cm REAL DEFAULT 0.0,
            alto_cm REAL DEFAULT 0.0,
            costo_calculado REAL DEFAULT 0.0,
            estado_envio TEXT NOT NULL DEFAULT 'En tránsito',
            recibido BOOLEAN NOT NULL DEFAULT 0,
            fecha_recibido DATE,
            FOREIGN KEY (articulo_id) REFERENCES articulos (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_operacion TEXT NOT NULL,
            articulo_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            moneda TEXT NOT NULL,
            tasa_cambio REAL NOT NULL,
            total_origen REAL NOT NULL,
            total_cup REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            sucursal TEXT DEFAULT 'Principal',
            FOREIGN KEY (articulo_id) REFERENCES articulos (id) ON DELETE RESTRICT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            articulo_id INTEGER NOT NULL,
            tipo_movimiento TEXT NOT NULL,
            cantidad REAL NOT NULL,
            sucursal TEXT DEFAULT 'Principal',
            usuario TEXT DEFAULT 'Sistema',
            FOREIGN KEY (articulo_id) REFERENCES articulos (id) ON DELETE RESTRICT
        )
    """)

    # 4. Índices para rendimiento extremo en consultas de agregación
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compras_articulo ON compras(articulo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compras_recibido ON compras(recibido)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_envios_articulo ON envios(articulo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_destinatarios_nombre ON destinatarios(nombre)")
    for column, definition in (
        ("modalidad_cobro", "TEXT NOT NULL DEFAULT 'Peso'"),
        ("peso_cobrado", "REAL DEFAULT 0.0"),
        ("largo_cm", "REAL DEFAULT 0.0"),
        ("ancho_cm", "REAL DEFAULT 0.0"),
        ("alto_cm", "REAL DEFAULT 0.0"),
        ("costo_calculado", "REAL DEFAULT 0.0"),
        ("estado_envio", "TEXT NOT NULL DEFAULT 'En tránsito'"),
    ):
        try:
            cursor.execute(f"ALTER TABLE envios ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).lower():
                raise
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_envios_modalidad ON envios(modalidad_cobro)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha_operacion)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_articulo ON ventas(articulo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos_inventario(fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_articulo ON movimientos_inventario(articulo_id)")

    cursor.execute("UPDATE envios SET estado_envio = CASE WHEN recibido = 1 THEN 'Entregado' ELSE 'En tránsito' END WHERE estado_envio IS NULL OR estado_envio = ''")
    
    # 6. Migración: Agregar columnas para cálculo de margen de ganancia en ventas
    try:
        cursor.execute("ALTER TABLE ventas ADD COLUMN numero_transaccion TEXT")
        logger.info("Columna 'numero_transaccion' agregada exitosamente a tabla ventas")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna numero_transaccion: {e}")
            raise
        else:
            logger.info("Columna 'numero_transaccion' ya existe en tabla ventas")
    
    try:
        cursor.execute("ALTER TABLE ventas ADD COLUMN costo_articulo REAL DEFAULT 0.0")
        logger.info("Columna 'costo_articulo' agregada exitosamente a tabla ventas")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna costo_articulo: {e}")
            raise
        else:
            logger.info("Columna 'costo_articulo' ya existe en tabla ventas")
    
    try:
        cursor.execute("ALTER TABLE ventas ADD COLUMN costo_logistico REAL DEFAULT 0.0")
        logger.info("Columna 'costo_logistico' agregada exitosamente a tabla ventas")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna costo_logistico: {e}")
            raise
        else:
            logger.info("Columna 'costo_logistico' ya existe en tabla ventas")
    
    try:
        cursor.execute("ALTER TABLE ventas ADD COLUMN margen_ganancia REAL DEFAULT 0.0")
        logger.info("Columna 'margen_ganancia' agregada exitosamente a tabla ventas")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna margen_ganancia: {e}")
            raise
        else:
            logger.info("Columna 'margen_ganancia' ya existe en tabla ventas")
    
    # 7. Migración: Agregar columna descripcion a articulos si no existe
    try:
        cursor.execute("PRAGMA table_info(articulos)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'descripcion' not in columns:
            cursor.execute("ALTER TABLE articulos ADD COLUMN descripcion TEXT DEFAULT ''")
            logger.info("Columna 'descripcion' agregada exitosamente a tabla articulos")
        else:
            logger.info("Columna 'descripcion' ya existe en tabla articulos")
    except sqlite3.OperationalError as e:
        logger.error(f"Error en migración de columna descripcion: {e}")

    # 7. Migración: Agregar columnas recibido y fecha_recibido a envios si no existen
    try:
        cursor.execute("ALTER TABLE envios ADD COLUMN recibido BOOLEAN NOT NULL DEFAULT 0")
        logger.info("Columna 'recibido' agregada exitosamente a tabla envios")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna recibido: {e}")
            raise
        else:
            logger.info("Columna 'recibido' ya existe en tabla envios")
    
    try:
        cursor.execute("ALTER TABLE envios ADD COLUMN fecha_recibido DATE")
        logger.info("Columna 'fecha_recibido' agregada exitosamente a tabla envios")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"Error en migración de columna fecha_recibido: {e}")
            raise
        else:
            logger.info("Columna 'fecha_recibido' ya existe en tabla envios")
    
    # 7. Migración: Cambiar columna destinatario_id a destinatario (TEXT) para coincidir con tabla destinatarios
    try:
        # Verificar si existe la columna destinatario_id
        cursor.execute("PRAGMA table_info(envios)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'destinatario_id' in columns:
            # Migrar datos de destinatario_id a destinatario (nombre)
            cursor.execute("""
                ALTER TABLE envios RENAME TO envios_old
            """)
            
            # Crear nueva tabla con la estructura correcta
            cursor.execute("""
                CREATE TABLE envios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    articulo_id INTEGER NOT NULL,
                    fecha DATE NOT NULL,
                    cantidad INTEGER NOT NULL DEFAULT 0,
                    destinatario TEXT,
                    metodo_envio TEXT,
                    costo_lb REAL DEFAULT 0.0,
                    recibido BOOLEAN NOT NULL DEFAULT 0,
                    fecha_recibido DATE,
                    FOREIGN KEY (articulo_id) REFERENCES articulos (id) ON DELETE CASCADE
                )
            """)
            
            # Migrar datos convirtiendo destinatario_id a nombre de destinatario
            cursor.execute("""
                INSERT INTO envios (id, articulo_id, fecha, cantidad, destinatario, metodo_envio, costo_lb, recibido, fecha_recibido)
                SELECT e.id, e.articulo_id, e.fecha, e.cantidad, d.nombre, e.metodo_envio, e.costo_lb, e.recibido, e.fecha_recibido
                FROM envios_old e
                LEFT JOIN destinatarios d ON e.destinatario_id = d.id
            """)
            
            # Eliminar tabla antigua
            cursor.execute("DROP TABLE envios_old")
            logger.info("Migración de destinatario_id a destinatario completada exitosamente")
        elif 'destinatario' not in columns:
            # Si no existe ninguna columna de destinatario, agregar la columna destinatario
            cursor.execute("ALTER TABLE envios ADD COLUMN destinatario TEXT")
            logger.info("Columna 'destinatario' agregada exitosamente a tabla envios")
        else:
            logger.info("Columna 'destinatario' ya existe en tabla envios")
            
    except sqlite3.OperationalError as e:
        logger.error(f"Error en migración de columna destinatario: {e}")
        # Si falla la migración compleja, intentar agregar la columna simplemente
        try:
            cursor.execute("ALTER TABLE envios ADD COLUMN destinatario TEXT")
            logger.info("Columna 'destinatario' agregada como fallback")
        except:
            logger.error("No se pudo agregar columna destinatario")
    
    # 8. Migración: Agregar columna numero a tabla destinatarios si no existe
    try:
        cursor.execute("PRAGMA table_info(destinatarios)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'numero' not in columns:
            cursor.execute("ALTER TABLE destinatarios ADD COLUMN numero TEXT")
            logger.info("Columna 'numero' agregada exitosamente a tabla destinatarios")
        else:
            logger.info("Columna 'numero' ya existe en tabla destinatarios")
    except sqlite3.OperationalError as e:
        logger.error(f"Error en migración de columna numero: {e}")
    
    # 9. Migración: Agregar columna activo a tabla destinatarios si no existe
    try:
        cursor.execute("PRAGMA table_info(destinatarios)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'activo' not in columns:
            cursor.execute("ALTER TABLE destinatarios ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")
            logger.info("Columna 'activo' agregada exitosamente a tabla destinatarios")
        else:
            logger.info("Columna 'activo' ya existe en tabla destinatarios")
    except sqlite3.OperationalError as e:
        logger.error(f"Error en migración de columna activo: {e}")

    # 10. Migración: Agregar columnas de control por cantidades parciales a tabla compras si no existe
    try:
        cursor.execute("PRAGMA table_info(compras)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'estado' not in columns:
            cursor.execute("ALTER TABLE compras ADD COLUMN estado TEXT NOT NULL DEFAULT 'Borrador'")
            logger.info("Columna 'estado' agregada exitosamente a tabla compras")
        else:
            logger.info("Columna 'estado' ya existe en tabla compras")

        if 'cantidad_recibida' not in columns:
            cursor.execute("ALTER TABLE compras ADD COLUMN cantidad_recibida INTEGER NOT NULL DEFAULT 0")
            logger.info("Columna 'cantidad_recibida' agregada exitosamente a tabla compras")
        else:
            logger.info("Columna 'cantidad_recibida' ya existe en tabla compras")

        if 'cantidad_cancelada' not in columns:
            cursor.execute("ALTER TABLE compras ADD COLUMN cantidad_cancelada INTEGER NOT NULL DEFAULT 0")
            logger.info("Columna 'cantidad_cancelada' agregada exitosamente a tabla compras")
        else:
            logger.info("Columna 'cantidad_cancelada' ya existe en tabla compras")

        cursor.execute("UPDATE compras SET cantidad_recibida = CASE WHEN recibido = 1 THEN cantidad ELSE 0 END WHERE cantidad_recibida IS NULL OR cantidad_recibida < 0")
        cursor.execute("UPDATE compras SET cantidad_cancelada = CASE WHEN estado IN (?, ?, ?) THEN cantidad ELSE 0 END WHERE cantidad_cancelada IS NULL OR cantidad_cancelada < 0", (
            PurchaseStatus.CANCELLED.value,
            PurchaseStatus.REFUNDED.value,
            PurchaseStatus.DEFECT_RETURNED.value,
        ))
    except sqlite3.OperationalError as e:
        logger.error(f"Error en migración de columnas de compra parcial: {e}")

    # 6. Tabla de Historial de Cambios (Audit Trail) para undo/redo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla TEXT NOT NULL,
            registro_id INTEGER NOT NULL,
            accion TEXT NOT NULL,
            valor_anterior TEXT,
            valor_nuevo TEXT,
            campo TEXT,
            usuario TEXT DEFAULT 'Sistema',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    """)
    
    # Índices para optimizar consultas de historial
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tabla ON audit_trail(tabla)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_registro ON audit_trail(registro_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_fecha ON audit_trail(fecha)")

    conn.commit()
    conn.close()


def registrar_movimiento(fecha, articulo_id, tipo_movimiento, cantidad,
                         sucursal="Principal", usuario="Sistema", conn=None):
    """Registra una entrada o salida en la bitácora de inventario."""
    owns_connection = conn is None
    connection = conn or get_connection()
    try:
        connection.execute(
            """
            INSERT INTO movimientos_inventario
                (fecha, articulo_id, tipo_movimiento, cantidad, sucursal, usuario)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fecha, articulo_id, tipo_movimiento, cantidad, sucursal, usuario),
        )
        if owns_connection:
            connection.commit()
        return True
    except sqlite3.Error as error:
        if owns_connection:
            connection.rollback()
        logger.error(f"Error al registrar movimiento de inventario: {error}")
        return False
    finally:
        if owns_connection:
            connection.close()

def get_inventory_summary(fecha_inicio=None, fecha_fin=None):
    """
    Consulta SQL central: Calcula el stock, el peso ponderado real y el precio ponderado real 
    basado en las compras históricas recibidas utilizando el ID del artículo.
    El campo recibido ahora muestra envíos recibidos, no compras recibidas.
    
    Args:
        fecha_inicio: Fecha de inicio para filtrar transacciones (formato YYYY-MM-DD)
        fecha_fin: Fecha de fin para filtrar transacciones (formato YYYY-MM-DD)
    """
    purchase_completed = PurchaseStatus.COMPLETED.value
    shipment_pending = _sql_values(ShipmentStatus.pending_values())
    shipment_completed = _sql_values(ShipmentStatus.completed_values())
    movement_in = _sql_values([
        InventoryMovementType.MANUAL_ENTRY.value,
        InventoryMovementType.TRANSFER_RECEIVED.value,
        InventoryMovementType.ADJUSTMENT_POSITIVE.value,
    ])
    movement_all = _sql_values([
        InventoryMovementType.MANUAL_ENTRY.value,
        InventoryMovementType.MANUAL_EXIT.value,
        InventoryMovementType.TRANSFER_RECEIVED.value,
        InventoryMovementType.TRANSFER_DELIVERED.value,
        InventoryMovementType.ADJUSTMENT_POSITIVE.value,
        InventoryMovementType.ADJUSTMENT_NEGATIVE.value,
        InventoryMovementType.SALE_EXIT.value,
    ])

    fecha_filter = ""
    params = []
    if fecha_inicio and fecha_fin:
        fecha_filter = "AND fecha BETWEEN ? AND ?"
        params = [fecha_inicio, fecha_fin]
    elif fecha_inicio:
        fecha_filter = "AND fecha >= ?"
        params = [fecha_inicio]
    elif fecha_fin:
        fecha_filter = "AND fecha <= ?"
        params = [fecha_fin]
    
    all_params = params * 7 if params else []
    
    query = f"""
        SELECT 
            a.id,
            a.nombre,
            a.categoria,
            COALESCE(a.peso_lb, 0.0) AS peso_lb,
            COALESCE(c_precios.precio_ponderado, 0.0) AS precio_ponderado,
            COALESCE(c_recibidas_almacen.total_recibido_almacen, 0) AS total_recibido,
            COALESCE(e_pendientes.total_transito, 0) AS total_transito,
            CASE
                WHEN (COALESCE(c_recibidas_almacen.total_recibido_almacen, 0)
                      - COALESCE(e_creados.total_creado, 0)) < 0 THEN 0
                ELSE (COALESCE(c_recibidas_almacen.total_recibido_almacen, 0)
                      - COALESCE(e_creados.total_creado, 0))
            END AS stock_a1,
            CASE
                WHEN ((COALESCE(c_recibidas_almacen.total_recibido_almacen, 0)
                       - COALESCE(e_creados.total_creado, 0))
                      + COALESCE(m_entradas.total_entrada, 0)
                      - COALESCE(m_salidas.total_salida, 0)) < 0 THEN 0
                ELSE ((COALESCE(c_recibidas_almacen.total_recibido_almacen, 0)
                       - COALESCE(e_creados.total_creado, 0))
                      + COALESCE(m_entradas.total_entrada, 0)
                      - COALESCE(m_salidas.total_salida, 0))
            END AS inventario
        FROM articulos a
        LEFT JOIN (
            SELECT 
                articulo_id, 
                SUM(cantidad_recibida * precio_unitario) * 1.0 / NULLIF(SUM(cantidad_recibida), 0) AS precio_ponderado
            FROM compras 
            WHERE cantidad_recibida > 0 AND estado = '{purchase_completed}' {{fecha_filter}}
            GROUP BY articulo_id
        ) c_precios ON a.id = c_precios.articulo_id
        LEFT JOIN (
            SELECT articulo_id, SUM(cantidad_recibida) as total_recibido_almacen 
            FROM compras 
            WHERE cantidad_recibida > 0 AND estado = '{purchase_completed}' {{fecha_filter}}
            GROUP BY articulo_id
        ) c_recibidas_almacen ON a.id = c_recibidas_almacen.articulo_id
        LEFT JOIN (
            SELECT articulo_id, SUM(cantidad) as total_transito 
            FROM envios 
            WHERE estado_envio IN ({shipment_pending})
              AND estado_envio != '{ShipmentStatus.CANCELLED.value}' {{fecha_filter}}
            GROUP BY articulo_id
        ) e_pendientes ON a.id = e_pendientes.articulo_id
        LEFT JOIN (
            SELECT articulo_id, SUM(cantidad) as total_creado 
            FROM envios 
            WHERE estado_envio IN ({shipment_pending}, {shipment_completed})
              AND estado_envio != '{ShipmentStatus.CANCELLED.value}' {{fecha_filter}}
            GROUP BY articulo_id
        ) e_creados ON a.id = e_creados.articulo_id
        LEFT JOIN (
            SELECT articulo_id, SUM(CASE
                WHEN tipo_movimiento IN ({movement_in}) THEN 0 ELSE cantidad END) AS total_salida
            FROM movimientos_inventario
            WHERE tipo_movimiento IN ({movement_all}) {{fecha_filter}}
            GROUP BY articulo_id
        ) m_salidas ON a.id = m_salidas.articulo_id
        LEFT JOIN (
            SELECT articulo_id, SUM(CASE
                WHEN tipo_movimiento IN ({movement_in}) THEN cantidad ELSE 0 END) AS total_entrada
            FROM movimientos_inventario
            WHERE tipo_movimiento IN ({movement_all}) {{fecha_filter}}
            GROUP BY articulo_id
        ) m_entradas ON a.id = m_entradas.articulo_id
        WHERE a.nombre NOT LIKE '\\_CATEGORIA\\_%' ESCAPE '\\'
    """
    
    query = query.format(fecha_filter=fecha_filter)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, all_params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def insert_compra(articulo_id, fecha, cantidad, precio_unitario, recibido=False, fecha_recibido=None, estado=None, cantidad_recibida=None, cantidad_cancelada=None):
    """Inserta una nueva compra relacionada al ID del artículo."""
    if estado is None:
        estado = PurchaseStatus.DRAFT.value
    if cantidad_recibida is None:
        cantidad_recibida = cantidad if bool(recibido) else 0
    if cantidad_cancelada is None:
        cantidad_cancelada = 0
    if recibido and fecha_recibido is None:
        fecha_recibido = date.today().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO compras (articulo_id, fecha, cantidad, precio_unitario, recibido, fecha_recibido, estado, cantidad_recibida, cantidad_cancelada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (articulo_id, fecha, cantidad, precio_unitario, recibido, fecha_recibido, estado, cantidad_recibida, cantidad_cancelada))
        conn.commit()  # Commit inmediato para asegurar persistencia

        if recibido:
            registrar_movimiento(fecha_recibido or fecha, articulo_id, "Entrada por compra", cantidad)
        
        # Registrar en audit trail
        from core.undo_redo import AuditLogger
        compra_id = cursor.lastrowid
        AuditLogger.log_change(
            tabla="compras",
            registro_id=compra_id,
            accion="INSERT",
            valor_anterior=None,
            valor_nuevo=f"articulo_id={articulo_id}, cantidad={cantidad}, precio={precio_unitario}",
            campo="compra_completa"
        )
        
        logger.info(f"Compra insertada exitosamente: artículo_id={articulo_id}, cantidad={cantidad}")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"Error de integridad al insertar compra: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    except sqlite3.Error as e:
        logger.error(f"Error de base de datos al insertar compra: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    except Exception as e:
        logger.error(f"Error inesperado al insertar compra: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        conn.close()

def insert_envio(articulo_id, fecha, cantidad, destinatario, metodo_envio, costo_lb=0.0, recibido=False, fecha_recibido=None):
    """Inserta un nuevo envío relacionado al ID del artículo con protección anti-apagones. destinatario es el nombre (TEXT)."""
    # Si se marca como recibido y no se proporciona fecha, usar fecha actual
    if recibido and fecha_recibido is None:
        fecha_recibido = date.today().isoformat()
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO envios (articulo_id, fecha, cantidad, destinatario, metodo_envio, costo_lb, recibido, fecha_recibido)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (articulo_id, fecha, cantidad, destinatario, metodo_envio, costo_lb, recibido, fecha_recibido))
        conn.commit()  # Commit inmediato para asegurar persistencia
        
        # Registrar en audit trail
        from core.undo_redo import AuditLogger
        envio_id = cursor.lastrowid
        AuditLogger.log_change(
            tabla="envios",
            registro_id=envio_id,
            accion="INSERT",
            valor_anterior=None,
            valor_nuevo=f"articulo_id={articulo_id}, cantidad={cantidad}, destinatario={destinatario}",
            campo="envio_completo"
        )
        
        logger.info(f"Envío insertado exitosamente: artículo_id={articulo_id}, cantidad={cantidad}, destinatario={destinatario}")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"Error de integridad al insertar envío: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    except sqlite3.Error as e:
        logger.error(f"Error de base de datos al insertar envío: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    except Exception as e:
        logger.error(f"Error inesperado al insertar envío: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        conn.close()

def insert_envios_batch(envios):
    """Inserta un lote de envíos en una única transacción.

    La reserva de stock A1 se calcula con los envíos creados, pero el descuento de
    inventario real solo debe registrarse cuando el envío queda en estado 'Entregado'.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for envio in envios:
            fecha_recibido = envio.get("fecha_recibido")
            estado_envio = envio.get("estado_envio", ShipmentStatus.IN_TRANSIT.value)
            if envio.get("recibido") and fecha_recibido is None:
                fecha_recibido = date.today().isoformat()
            cursor.execute("""
                INSERT INTO envios (
                    articulo_id, fecha, cantidad, destinatario, metodo_envio,
                    costo_lb, modalidad_cobro, peso_cobrado, largo_cm, ancho_cm,
                    alto_cm, costo_calculado, recibido, fecha_recibido
                    , estado_envio
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                envio["articulo_id"], envio["fecha"], envio["cantidad"],
                envio["destinatario"], envio["metodo_envio"], envio["costo_lb"],
                envio.get("modalidad_cobro", "Peso"), envio.get("peso_cobrado", 0.0),
                envio.get("largo_cm", 0.0), envio.get("ancho_cm", 0.0),
                envio.get("alto_cm", 0.0), envio.get("costo_calculado", envio["costo_lb"]),
                envio["recibido"], fecha_recibido, estado_envio
            ))
            if estado_envio == ShipmentStatus.DELIVERED.value and not envio.get("recibido", False):
                # Seguridad: si el estado es Entregado, el registro debe reflejar la entrega real.
                envio["recibido"] = True
            if estado_envio == ShipmentStatus.DELIVERED.value:
                registrar_movimiento(
                    envio["fecha"], envio["articulo_id"], InventoryMovementType.SHIPMENT_EXIT.value, envio["cantidad"],
                    envio.get("sucursal", "Principal"), envio.get("usuario", "Sistema"), conn
                )
        conn.commit()
        return True
    except sqlite3.Error as error:
        logger.error(f"Error al insertar lote de envíos: {error}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_articulos():
    """Retorna todos los artículos para usar en combobox (autocompletado en compras)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, categoria, descripcion, peso_lb
            FROM articulos
            WHERE nombre NOT LIKE '\\_CATEGORIA\\_%' ESCAPE '\\'
            ORDER BY nombre
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener artículos: {e}")
        return []
    finally:
        if conn:
            conn.close()

def insert_articulo(nombre, categoria="General", peso_lb=0.0, descripcion=""):
    """Inserta un nuevo artículo en el catálogo con protección anti-apagones. Retorna el ID del artículo creado o None en caso de error."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        peso_lb = normalize_decimal(peso_lb)
        descripcion = (descripcion or "").strip()
        cursor.execute("""
            INSERT INTO articulos (nombre, categoria, descripcion, peso_lb)
            VALUES (?, ?, ?, ?)
        """, (nombre, categoria, descripcion, peso_lb))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return cursor.lastrowid  # Retornar el ID del artículo creado
    except Exception as e:
        logger.error(f"Error al insertar artículo: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return None
    finally:
        if conn:
            conn.close()

def update_articulo(articulo_id, nombre, categoria, peso_lb, descripcion=""):
    """Actualiza un artículo existente por su ID con protección anti-apagones."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        peso_lb = normalize_decimal(peso_lb)
        descripcion = (descripcion or "").strip()
        cursor.execute("""
            UPDATE articulos 
            SET nombre = ?, categoria = ?, descripcion = ?, peso_lb = ?
            WHERE id = ?
        """, (nombre, categoria, descripcion, peso_lb, articulo_id))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return True
    except Exception as e:
        logger.error(f"Error al actualizar artículo: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        if conn:
            conn.close()

def delete_articulo(articulo_id):
    """Elimina un artículo por su ID con protección anti-apagones."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM compras WHERE articulo_id = ?) "
            "OR EXISTS(SELECT 1 FROM envios WHERE articulo_id = ?)",
            (articulo_id, articulo_id)
        )
        if cursor.fetchone()[0]:
            logger.warning(f"Artículo {articulo_id} no eliminado: tiene historial asociado")
            return False
        cursor.execute("DELETE FROM articulos WHERE id = ?", (articulo_id,))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return True
    except Exception as e:
        logger.error(f"Error al eliminar artículo: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        if conn:
            conn.close()

def get_articulo_by_id(articulo_id):
    """Obtiene un artículo específico por su ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, categoria, descripcion, peso_lb
            FROM articulos 
            WHERE id = ?
        """, (articulo_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error al obtener artículo por ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_compra(compra_id, articulo_id, fecha, cantidad, precio_unitario, recibido, fecha_recibido=None, estado=None, cantidad_recibida=None, cantidad_cancelada=None):
    """Actualiza una compra existente con protección anti-apagones."""
    cancelled_states = [
        PurchaseStatus.CANCELLED.value,
        PurchaseStatus.REFUNDED.value,
        PurchaseStatus.DEFECT_RETURNED.value,
    ]

    if cantidad_recibida is None:
        cantidad_recibida = cantidad if bool(recibido) else 0
    if cantidad_cancelada is None:
        cantidad_cancelada = cantidad if estado in cancelled_states else 0

    cantidad_recibida = max(0, int(cantidad_recibida))
    cantidad_cancelada = max(0, int(cantidad_cancelada))
    if cantidad_recibida + cantidad_cancelada > int(cantidad):
        cantidad_cancelada = max(0, int(cantidad) - cantidad_recibida)

    if recibido and fecha_recibido is None:
        fecha_recibido = date.today().isoformat()
    if not recibido:
        fecha_recibido = None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        previous = cursor.execute(
            "SELECT recibido, estado, cantidad_recibida, cantidad_cancelada FROM compras WHERE id = ?", (compra_id,)
        ).fetchone()

        effective_estado = estado

        if effective_estado in cancelled_states and cantidad_recibida == 0 and cantidad_cancelada == int(cantidad):
            recibido = 0
            fecha_recibido = None
            cantidad_recibida = 0
            cantidad_cancelada = int(cantidad)
        elif cantidad_recibida > 0:
            recibido = 1
            if fecha_recibido is None:
                fecha_recibido = date.today().isoformat()
        elif effective_estado == PurchaseStatus.COMPLETED.value:
            recibido = 1
            if fecha_recibido is None:
                fecha_recibido = date.today().isoformat()
            cantidad_recibida = int(cantidad)

        if cantidad_recibida + cantidad_cancelada > int(cantidad):
            cantidad_cancelada = max(0, int(cantidad) - cantidad_recibida)

        if effective_estado is not None:
            cursor.execute("""
                UPDATE compras 
                SET articulo_id = ?, fecha = ?, cantidad = ?, precio_unitario = ?, recibido = ?, fecha_recibido = ?, estado = ?, cantidad_recibida = ?, cantidad_cancelada = ?
                WHERE id = ?
            """, (articulo_id, fecha, cantidad, precio_unitario, int(bool(recibido)), fecha_recibido, effective_estado, cantidad_recibida, cantidad_cancelada, compra_id))
        else:
            cursor.execute("""
                UPDATE compras 
                SET articulo_id = ?, fecha = ?, cantidad = ?, precio_unitario = ?, recibido = ?, fecha_recibido = ?, cantidad_recibida = ?, cantidad_cancelada = ?
                WHERE id = ?
            """, (articulo_id, fecha, cantidad, precio_unitario, int(bool(recibido)), fecha_recibido, cantidad_recibida, cantidad_cancelada, compra_id))

        conn.commit()

        current_received = int(cantidad_recibida or 0)
        if previous:
            previous_received = int(previous["cantidad_recibida"] or 0)
            delta = current_received - previous_received
            if delta > 0:
                registrar_movimiento(
                    fecha_recibido or fecha, articulo_id, InventoryMovementType.PURCHASE_ENTRY.value, delta, conn=conn
                )
            elif delta < 0:
                registrar_movimiento(
                    date.today().isoformat(), articulo_id, InventoryMovementType.PURCHASE_REVERSAL.value, abs(delta), conn=conn
                )
        elif int(bool(recibido)):
            registrar_movimiento(
                fecha_recibido or fecha, articulo_id, InventoryMovementType.PURCHASE_ENTRY.value, current_received, conn=conn
            )

        return True
    except Exception as e:
        logger.error(f"Error al actualizar compra: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_compra(compra_id):
    """Elimina una compra por su ID con protección anti-apagones."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return True
    except Exception as e:
        logger.error(f"Error al eliminar compra: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        if conn:
            conn.close()

def delete_compras_batch(compra_ids):
    """Elimina múltiples compras en una sola transacción."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(compra_ids))
        cursor.execute(f"DELETE FROM compras WHERE id IN ({placeholders})", compra_ids)
        conn.commit()
        logger.info(f"Eliminadas {cursor.rowcount} compras en lote")
        return True
    except Exception as e:
        logger.error(f"Error al eliminar compras en lote: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_compras_estado_batch(compra_ids, nuevo_estado):
    """Actualiza el estado de múltiples compras en una sola transacción."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(compra_ids))
        cancelled_states = [
            PurchaseStatus.CANCELLED.value,
            PurchaseStatus.REFUNDED.value,
            PurchaseStatus.DEFECT_RETURNED.value,
        ]
        
        cursor.execute(f"SELECT id, articulo_id, cantidad, recibido FROM compras WHERE id IN ({placeholders})", compra_ids)
        compras_anteriores = cursor.fetchall()
        
        cursor.execute(f"UPDATE compras SET estado = ? WHERE id IN ({placeholders})", [nuevo_estado] + compra_ids)
        
        if nuevo_estado == PurchaseStatus.COMPLETED.value:
            for compra in compras_anteriores:
                if not compra['recibido']:
                    cursor.execute("""
                        UPDATE compras 
                        SET recibido = 1, fecha_recibido = ?, cantidad_recibida = cantidad, cantidad_cancelada = 0
                        WHERE id = ?
                    """, (date.today().isoformat(), compra['id']))
                    registrar_movimiento(date.today().isoformat(), compra['articulo_id'], InventoryMovementType.PURCHASE_ENTRY.value, compra['cantidad'], conn=conn)

        for compra in compras_anteriores:
            if compra['recibido'] and nuevo_estado in cancelled_states:
                registrar_movimiento(date.today().isoformat(), compra['articulo_id'], InventoryMovementType.PURCHASE_REVERSAL.value, compra['cantidad'], conn=conn)
                cursor.execute("""
                    UPDATE compras 
                    SET recibido = 0, fecha_recibido = NULL, cantidad_recibida = 0, cantidad_cancelada = cantidad
                    WHERE id = ?
                """, (compra['id'],))
        
        conn.commit()
        logger.info(f"Actualizados {cursor.rowcount} compras a estado '{nuevo_estado}'")
        return True
    except Exception as e:
        logger.error(f"Error al actualizar estados de compras en lote: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_envio(envio_id, articulo_id, fecha, cantidad, destinatario, metodo_envio,
                 costo_lb, recibido=False, fecha_recibido=None,
                 modalidad_cobro="Peso", peso_cobrado=0.0, largo_cm=0.0,
                 ancho_cm=0.0, alto_cm=0.0, costo_calculado=None,
                 estado_envio=None):
    """Actualiza un envío existente con protección anti-apagones. destinatario es el nombre (TEXT)."""
    if estado_envio is None:
        estado_envio = ShipmentStatus.IN_TRANSIT.value
    # Si se marca como recibido y no se proporciona fecha, usar fecha actual
    if recibido and fecha_recibido is None:
        fecha_recibido = date.today().isoformat()
    # Si se desmarca como recibido, limpiar fecha_recibido
    if not recibido:
        fecha_recibido = None
    if costo_calculado is None:
        costo_calculado = costo_lb
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE envios
            SET articulo_id = ?, fecha = ?, cantidad = ?, destinatario = ?, metodo_envio = ?,
                costo_lb = ?, modalidad_cobro = ?, peso_cobrado = ?, largo_cm = ?,
                ancho_cm = ?, alto_cm = ?, costo_calculado = ?, estado_envio = ?,
                recibido = ?, fecha_recibido = ?
            WHERE id = ?
        """, (articulo_id, fecha, cantidad, destinatario, metodo_envio, costo_lb,
               modalidad_cobro, peso_cobrado, largo_cm, ancho_cm, alto_cm,
               costo_calculado, estado_envio, recibido, fecha_recibido, envio_id))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return True
    except Exception as e:
        logger.error(f"Error al actualizar envío: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        if conn:
            conn.close()

def delete_envio(envio_id):
    """Elimina un envío por su ID con protección anti-apagones."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM envios WHERE id = ?", (envio_id,))
        conn.commit()  # Commit inmediato para asegurar persistencia
        return True
    except Exception as e:
        logger.error(f"Error al eliminar envío: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        if conn:
            conn.close()

def delete_envios_batch(envio_ids):
    """Elimina múltiples envíos en una sola transacción."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(envio_ids))
        cursor.execute(f"DELETE FROM envios WHERE id IN ({placeholders})", envio_ids)
        conn.commit()
        logger.info(f"Eliminados {cursor.rowcount} envíos en lote")
        return True
    except Exception as e:
        logger.error(f"Error al eliminar envíos en lote: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_envios_estado_batch(envio_ids, nuevo_estado):
    """Actualiza el estado de múltiples envíos en una sola transacción.

    El stock A1 se consume cuando resulta un envío creado; el inventario real solo se
    descuenta cuando ese envío pasa a estado Entregado.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(envio_ids))

        cursor.execute(f"SELECT id, articulo_id, cantidad, estado_envio FROM envios WHERE id IN ({placeholders})", envio_ids)
        envios_anteriores = cursor.fetchall()
        estado_delivered = ShipmentStatus.DELIVERED.value

        if nuevo_estado == estado_delivered:
            for envio in envios_anteriores:
                if envio["estado_envio"] != estado_delivered:
                    registrar_movimiento(
                        date.today().isoformat(),
                        envio["articulo_id"],
                        InventoryMovementType.SHIPMENT_EXIT.value,
                        envio["cantidad"],
                        "Principal",
                        "Sistema",
                        conn,
                    )
            cursor.execute(f"""
                UPDATE envios 
                SET estado_envio = ?, recibido = 1, fecha_recibido = ?
                WHERE id IN ({placeholders})
            """, [nuevo_estado, date.today().isoformat()] + envio_ids)
        else:
            cursor.execute(f"UPDATE envios SET estado_envio = ? WHERE id IN ({placeholders})", [nuevo_estado] + envio_ids)

        conn.commit()
        logger.info(f"Actualizados {cursor.rowcount} envíos a estado '{nuevo_estado}'")
        return True
    except Exception as e:
        logger.error(f"Error al actualizar estados de envíos en lote: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_compra_by_id(compra_id):
    """Retorna los datos de una compra por su ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM compras WHERE id = ?", (compra_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error al obtener compra por ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_envio_by_id(envio_id):
    """Retorna los datos de un envío por su ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM envios WHERE id = ?", (envio_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error al obtener envío por ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_articulos_disponibles():
    """
    Retorna artículos con stock neto disponible basado en el Stock A1 real:
    compras recibidas completadas menos envíos creados (pendientes + completados).
    """
    purchase_completed = PurchaseStatus.COMPLETED.value
    shipment_states = _sql_values(ShipmentStatus.pending_values() + ShipmentStatus.completed_values())
    query = f"""
        WITH stock_por_articulo AS (
            SELECT a.id,
                   a.nombre,
                   a.categoria,
                   a.peso_lb,
                   (
                       COALESCE((SELECT SUM(c.cantidad_recibida)
                                 FROM compras c
                                 WHERE c.articulo_id = a.id
                                   AND c.cantidad_recibida > 0
                                   AND c.estado = '{purchase_completed}'), 0)
                       -
                       COALESCE((SELECT SUM(e.cantidad)
                                 FROM envios e
                                 WHERE e.articulo_id = a.id
                                   AND e.estado_envio IN ({shipment_states})
                                   AND e.estado_envio != '{ShipmentStatus.CANCELLED.value}'), 0)
                   ) AS stock_disponible
            FROM articulos a
            WHERE a.nombre NOT LIKE '\\_CATEGORIA\\_%' ESCAPE '\\'
        )
        SELECT id, nombre, categoria, peso_lb, stock_disponible
        FROM stock_por_articulo
        WHERE stock_disponible > 0
        ORDER BY nombre
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener artículos disponibles: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_stock_disponible(articulo_id):
    """
    Stock disponible del almacén A1: compras recibidas menos salidas creadas.
    Este valor se usa para validar envíos desde A1.
    """
    purchase_completed = PurchaseStatus.COMPLETED.value
    shipment_states = _sql_values(ShipmentStatus.pending_values() + ShipmentStatus.completed_values())
    query = f"""
        SELECT (
            COALESCE((SELECT SUM(cantidad_recibida)
                      FROM compras
                      WHERE articulo_id = ?
                        AND cantidad_recibida > 0
                        AND estado = '{purchase_completed}'), 0)
            - COALESCE((SELECT SUM(cantidad)
                        FROM envios
                        WHERE articulo_id = ?
                          AND estado_envio IN ({shipment_states})
                          AND estado_envio != '{ShipmentStatus.CANCELLED.value}'), 0)
        ) AS stock
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        result = cursor.execute(query, (articulo_id, articulo_id)).fetchone()
        stock = float((result['stock'] if result else 0) or 0)
        return max(0, int(stock))
    except Exception as e:
        logger.error(f"Error al obtener stock disponible: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def get_costo_total_articulo(articulo_id):
    """Calcula el costo total del artículo sumando el costo del artículo más el costo logístico promedio (flete)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Obtener precio ponderado del artículo desde compras
        cursor.execute("""
            SELECT COALESCE(SUM(cantidad_recibida * precio_unitario) / NULLIF(SUM(cantidad_recibida), 0), 0) AS precio_ponderado
            FROM compras
            WHERE articulo_id = ? AND cantidad_recibida > 0 AND estado = 'Completada'
        """, (articulo_id,))
        precio_articulo = float(cursor.fetchone()['precio_ponderado'] or 0)
        
        # Obtener costo logístico promedio (flete) desde envíos
        cursor.execute("""
            SELECT COALESCE(SUM(costo_calculado) / NULLIF(SUM(cantidad), 0), 0) AS costo_flete_promedio
            FROM envios
            WHERE articulo_id = ? AND cantidad > 0 AND costo_calculado > 0
        """, (articulo_id,))
        costo_flete = float(cursor.fetchone()['costo_flete_promedio'] or 0)
        
        costo_total = precio_articulo + costo_flete
        return costo_total
    except Exception as e:
        logger.error(f"Error al calcular costo total del artículo: {e}")
        return 0.0
    finally:
        conn.close()


def get_inventario_disponible(articulo_id):
    """Inventario operativo real disponible para venta o movimiento interno."""
    movement_in = _sql_values([
        InventoryMovementType.MANUAL_ENTRY.value,
        InventoryMovementType.TRANSFER_RECEIVED.value,
        InventoryMovementType.ADJUSTMENT_POSITIVE.value,
        InventoryMovementType.PURCHASE_ENTRY.value,
    ])
    movement_out = _sql_values([
        InventoryMovementType.MANUAL_EXIT.value,
        InventoryMovementType.TRANSFER_DELIVERED.value,
        InventoryMovementType.ADJUSTMENT_NEGATIVE.value,
        InventoryMovementType.SALE_EXIT.value,
        InventoryMovementType.PURCHASE_REVERSAL.value,
    ])
    query = f"""
        SELECT (
            COALESCE((SELECT SUM(cantidad_recibida)
                      FROM compras
                      WHERE articulo_id = ?
                        AND cantidad_recibida > 0
                        AND estado = '{PurchaseStatus.COMPLETED.value}'), 0)
            - COALESCE((SELECT SUM(cantidad)
                        FROM envios
                        WHERE articulo_id = ?
                          AND estado_envio IN ({_sql_values(ShipmentStatus.pending_values() + ShipmentStatus.completed_values())})
                          AND estado_envio != '{ShipmentStatus.CANCELLED.value}'), 0)
            + COALESCE((SELECT SUM(cantidad)
                        FROM movimientos_inventario
                        WHERE articulo_id = ?
                          AND tipo_movimiento IN ({movement_in})), 0)
            - COALESCE((SELECT SUM(cantidad)
                        FROM movimientos_inventario
                        WHERE articulo_id = ?
                          AND tipo_movimiento IN ({movement_out})), 0)
            - COALESCE((SELECT SUM(cantidad)
                        FROM ventas
                        WHERE articulo_id = ?), 0)
        ) AS stock
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        result = cursor.execute(query, (articulo_id, articulo_id, articulo_id, articulo_id, articulo_id)).fetchone()
        stock = float((result['stock'] if result else 0) or 0)
        return max(0, int(stock))
    except Exception as e:
        logger.error(f"Error al obtener inventario disponible: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def registrar_venta(fecha_operacion, articulo_id, cantidad, precio_unitario,
                    moneda, tasa_cambio, total_origen, total_cup,
                    metodo_pago, sucursal="Principal", numero_transaccion=None,
                    costo_articulo=0.0, costo_logistico=0.0, margen_ganancia=0.0):
    """Valida existencias e inserta una venta en una única transacción SQLite."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT COALESCE((SELECT SUM(cantidad_recibida) FROM compras
                             WHERE articulo_id = ? AND cantidad_recibida > 0 AND estado = 'Completada'), 0)
                 - COALESCE((SELECT SUM(cantidad) FROM envios
                             WHERE articulo_id = ?
                               AND estado_envio IN (?, ?, ?, ?)
                               AND estado_envio != 'Cancelado'), 0)
                 - COALESCE((SELECT SUM(cantidad) FROM ventas
                             WHERE articulo_id = ?), 0) AS stock
            """,
            (articulo_id, articulo_id,
             ShipmentStatus.IN_TRANSIT.value,
             ShipmentStatus.DELIVERED.value,
             ShipmentStatus.RETURNED.value,
             ShipmentStatus.CANCELLED.value,
             articulo_id),
        ).fetchone()
        stock = max(0.0, float(row["stock"] or 0))
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if cantidad > stock:
            raise ValueError(f"Stock insuficiente. Disponible: {stock:g}.")

        cursor = conn.execute(
            """
            INSERT INTO ventas (
                fecha_operacion, articulo_id, cantidad, precio_unitario,
                moneda, tasa_cambio, total_origen, total_cup,
                metodo_pago, sucursal, numero_transaccion, costo_articulo,
                costo_logistico, margen_ganancia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fecha_operacion, articulo_id, cantidad, precio_unitario,
             moneda, tasa_cambio, total_origen, total_cup,
             metodo_pago, sucursal, numero_transaccion, costo_articulo,
             costo_logistico, margen_ganancia),
        )
        conn.commit()
        registrar_movimiento(
            fecha_operacion, articulo_id, InventoryMovementType.SALE_EXIT.value, cantidad,
            sucursal, "Sistema", conn
        )
        conn.commit()
        return True, "Venta registrada correctamente.", cursor.lastrowid
    except (sqlite3.Error, ValueError) as error:
        conn.rollback()
        return False, str(error), None
    finally:
        conn.close()


def delete_venta(venta_id):
    """Elimina una venta y restaura el stock en una transacción atómica."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        # Obtener datos de la venta antes de eliminar
        venta = conn.execute(
            "SELECT articulo_id, cantidad, fecha_operacion, sucursal FROM ventas WHERE id = ?",
            (venta_id,)
        ).fetchone()
        
        if not venta:
            raise ValueError("Venta no encontrada.")
        
        articulo_id = venta["articulo_id"]
        cantidad = venta["cantidad"]
        fecha_operacion = venta["fecha_operacion"]
        sucursal = venta["sucursal"]
        
        # Eliminar la venta
        conn.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))
        
        # Restaurar el stock mediante un movimiento de entrada
        registrar_movimiento(
            fecha_operacion, articulo_id, "Reversión de venta", cantidad,
            sucursal, "Sistema", conn
        )
        
        conn.commit()
        logger.info(f"Venta {venta_id} eliminada y stock restaurado correctamente")
        return True
    except (sqlite3.Error, ValueError) as error:
        conn.rollback()
        logger.error(f"Error al eliminar venta {venta_id}: {error}")
        return False
    finally:
        conn.close()

# --- CRUD PARA DESTINATARIOS ---

def get_destinatarios():
    """Retorna todos los destinatarios activos."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, nombre, direccion, numero, telefono, email, notas, fecha_registro, activo
            FROM destinatarios
            WHERE activo = 1
            ORDER BY nombre
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener destinatarios: {e}")
        return []
    finally:
        conn.close()

def get_destinatario_by_nombre(nombre):
    """Retorna un destinatario por su nombre."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM destinatarios WHERE nombre = ?", (nombre,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error al obtener destinatario por nombre: {e}")
        return None
    finally:
        conn.close()

def get_destinatario_by_id(destinatario_id):
    """Retorna un destinatario específico por ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, nombre, direccion, numero, telefono, email, notas, fecha_registro, activo
            FROM destinatarios
            WHERE id = ?
        """, (destinatario_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error al obtener destinatario por ID: {e}")
        return None
    finally:
        conn.close()

def buscar_destinatario_por_nombre(nombre):
    """Busca destinatarios por nombre (búsqueda parcial)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, nombre, direccion, numero, telefono, email
            FROM destinatarios
            WHERE activo = 1 AND nombre LIKE ?
            ORDER BY nombre
        """, (f"%{nombre}%",))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al buscar destinatarios: {e}")
        return []
    finally:
        conn.close()

def insert_destinatario(nombre, direccion="", numero="", telefono=None, email=None, notas=None):
    """Inserta un nuevo destinatario con protección anti-apagones y retorna su ID o None si falla."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO destinatarios (nombre, direccion, numero, telefono, email, notas, fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nombre, direccion, numero, telefono, email, notas, date.today().isoformat()))
        conn.commit()  # Commit inmediato para asegurar persistencia
        
        nuevo_id = cursor.lastrowid
        
        # Registrar en audit trail
        from core.undo_redo import AuditLogger
        AuditLogger.log_change(
            tabla="destinatarios",
            registro_id=nuevo_id,
            accion="INSERT",
            valor_anterior=None,
            valor_nuevo=f"nombre={nombre}, direccion={direccion}",
            campo="destinatario_completo"
        )
        
        logger.info(f"Destinatario insertado: {nombre} (ID: {nuevo_id})")
        return nuevo_id
    except sqlite3.IntegrityError:
        logger.error(f"El destinatario '{nombre}' ya existe.")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return None
    except Exception as e:
        logger.error(f"Error al insertar destinatario: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return None
    finally:
        conn.close()

def update_destinatario(destinatario_id, nombre, direccion="", numero="", telefono=None, email=None, notas=None):
    """Actualiza un destinatario existente con protección anti-apagones."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE destinatarios 
            SET nombre = ?, direccion = ?, numero = ?, telefono = ?, email = ?, notas = ?
            WHERE id = ?
        """, (nombre, direccion, numero, telefono, email, notas, destinatario_id))
        conn.commit()  # Commit inmediato para asegurar persistencia
        affected_rows = cursor.rowcount
        
        logger.info(f"Destinatario actualizado: {nombre} (ID: {destinatario_id})")
        return affected_rows > 0
    except Exception as e:
        logger.error(f"Error al actualizar destinatario: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        conn.close()

def delete_destinatario(destinatario_id):
    """Elimina (desactiva) un destinatario usando soft delete con protección anti-apagones."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Soft delete: marcar como inactivo en lugar de eliminar
        cursor.execute("""
            UPDATE destinatarios
            SET activo = 0
            WHERE id = ?
        """, (destinatario_id,))
        conn.commit()  # Commit inmediato para asegurar persistencia
        affected_rows = cursor.rowcount
        
        logger.info(f"Destinatario desactivado: ID {destinatario_id}")
        return affected_rows > 0
    except Exception as e:
        logger.error(f"Error al eliminar destinatario: {e}")
        conn.rollback()  # Rollback en caso de error para evitar corrupción
        return False
    finally:
        conn.close()