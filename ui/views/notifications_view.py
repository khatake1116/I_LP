# ui/views/notifications_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHBoxLayout, QHeaderView,
                             QLabel, QSpinBox, QGroupBox)
from PySide6.QtCore import Qt
from datetime import datetime, date
import json
from core.paths import get_config_path
from database.connection import get_connection

class NotificationsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Panel de Mini-Configuración (Umbral de días) - REMOVIDO, ahora en Configuración
        info_label = QLabel("⚙️ Configure los umbrales de alertas en el módulo de Configuración")
        info_label.setObjectName("NotificationsInfo")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        # Tabla de Notificaciones / Alertas activas
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Tipo", "Artículo", "Fecha de Registro", "Alerta y Días de Retraso"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Label para estado vacío
        self.empty_label = QLabel("No hay notificaciones pendientes")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setObjectName("NotificationsEmpty")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)
        
        self.dias_limite_compras, self.dias_limite_envios = self.load_alert_settings()
        
        self.load_alerts()

    def load_alert_settings(self):
        """Carga los umbrales de alertas desde config.json."""
        try:
            with get_config_path().open("r", encoding="utf-8") as config_file:
                config = json.load(config_file)
            return (
                config.get("dias_alerta_compras", 7),
                config.get("dias_alerta_envios", 15),
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return 7, 15

    def load_alerts(self):
        """Calcula y carga las alertas basadas en los umbrales configurados."""
        hoy = date.today()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        alertas = []

        # 1. Consultar Compras pendientes (recibido = 0)
        query_compras = """
            SELECT c.fecha, a.nombre, c.cantidad
            FROM compras c
            LEFT JOIN articulos a ON c.articulo_id = a.id
            WHERE c.recibido = 0
        """
        cursor.execute(query_compras)
        compras = cursor.fetchall()

        for row in compras:
            fecha_str = row['fecha']
            nombre = row['nombre']
            
            try:
                fecha_reg = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                dias_transcurridos = (hoy - fecha_reg).days
                
                if dias_transcurridos > self.dias_limite_compras:
                    retraso = dias_transcurridos - self.dias_limite_compras
                    mensaje = f"El producto {nombre} aún no ha llegado a Stock A1 (Retraso de {retraso} días extra)"
                    alertas.append({
                        "tipo": "Compra Pendiente",
                        "articulo": nombre,
                        "fecha": fecha_str,
                        "mensaje": mensaje,
                        "retraso": retraso
                    })
            except Exception as e:
                print(f"Error procesando fecha de compra: {e}")

        # 2. Consultar Envíos pendientes
        try:
            query_envios = """
                SELECT e.fecha, a.nombre 
                FROM envios e
                LEFT JOIN articulos a ON e.articulo_id = a.id
                WHERE e.recibido = 0
            """
            cursor.execute(query_envios)
            envios = cursor.fetchall()

            for row in envios:
                fecha_str = row['fecha'] if 'fecha' in row.keys() else str(hoy)
                nombre = row['nombre']
                
                fecha_reg = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                dias_transcurridos = (hoy - fecha_reg).days
                
                if dias_transcurridos > self.dias_limite_envios:
                    retraso = dias_transcurridos - self.dias_limite_envios
                    mensaje = f"El producto {nombre} aún está en tránsito. Comprueba la ruta (Retraso de {retraso} días extra)"
                    alertas.append({
                        "tipo": "Envío en Tránsito",
                        "articulo": nombre,
                        "fecha": fecha_str,
                        "mensaje": mensaje,
                        "retraso": retraso
                    })
        except Exception:
            pass  # Si la tabla envios no tiene fecha todavía

        conn.close()

        # Mostrar/ocultar tabla y label de estado vacío
        if len(alertas) == 0:
            self.table.setVisible(False)
            self.empty_label.setVisible(True)
        else:
            self.table.setVisible(True)
            self.empty_label.setVisible(False)
            
            # Poblar la tabla de alertas
            self.table.setRowCount(len(alertas))
            for row_idx, alt in enumerate(alertas):
                item_tipo = QTableWidgetItem(alt['tipo'])
                item_tipo.setForeground(Qt.red if "Compra" in alt['tipo'] else Qt.yellow)
                
                self.table.setItem(row_idx, 0, item_tipo)
                self.table.setItem(row_idx, 1, QTableWidgetItem(alt['articulo']))
                self.table.setItem(row_idx, 2, QTableWidgetItem(alt['fecha']))
                self.table.setItem(row_idx, 3, QTableWidgetItem(alt['mensaje']))

    def closeEvent(self, event):
        """Detener timers al cerrar la vista para prevenir memory leaks."""
        super().closeEvent(event)