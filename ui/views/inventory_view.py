# ui/views/inventory_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, QHBoxLayout,
                             QDialog, QFormLayout, QMessageBox, QLabel, 
                             QTabWidget, QGridLayout, QFrame)
from PySide6.QtCore import Qt
from datetime import datetime, date
from database.models import get_inventory_summary
from database.connection import get_connection
from core.formatting import format_money, format_custom_number
from ui.views.base_view import BaseRefreshView


class InventoryView(BaseRefreshView):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Verificar coherencia de fecha del sistema con DB
        self.check_system_date_coherence()

        # Widget de pestañas principal (único nivel)
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("InventoryTabWidget")
        
        # Pestaña 1: Dashboard (KPIs y alertas)
        self.dashboard_tab = self.create_dashboard_tab()
        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")

        # Pestaña 2: Existencias (tabla principal)
        self.existencias_tab = self.create_existencias_tab()
        self.tab_widget.addTab(self.existencias_tab, "Existencias")
        
        # Pestaña 3: Movimientos (historial de movimientos)
        from ui.views.inventory_movements_view import InventoryMovementsView
        self.movements_tab = InventoryMovementsView()
        self.tab_widget.addTab(self.movements_tab, "Movimiento")
        
        layout.addWidget(self.tab_widget)
        
        # Cargar datos iniciales
        self.load_data()

    def create_existencias_tab(self):
        """Crea la pestaña de tabla de existencias."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Configuración de la tabla con columnas simplificadas (6 columnas)
        self.table = QTableWidget()
        self.table.setObjectName("InventoryTable")
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Artículo", "Prec. Ponderado", "Prec. Pesaje Pond.", 
            "Stock A1", "Stock en Tránsito", "Inventario"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.on_double_click)

        layout.addWidget(self.table)
        return tab

    def create_dashboard_tab(self):
        """Crea la pestaña de Dashboard de Inventario con KPIs y alertas."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Tarjetas KPI de Inventario
        inventory_cards_layout = QGridLayout()
        inventory_cards_layout.setSpacing(12)
        self.inventory_metric_values = {}
        
        self.add_metric(inventory_cards_layout, "inventory_value_cup", "Valor Total Inventario (CUP)", "0.00 CUP", 0, 0)
        self.add_metric(inventory_cards_layout, "inventory_value_usd", "Valor Total Inventario (USD)", "0.00 USD", 0, 1)
        self.add_metric(inventory_cards_layout, "total_stock_a1", "Total Artículos Stock A1", "0", 1, 0)
        self.add_metric(inventory_cards_layout, "in_transit", "Artículos en Tránsito", "0", 1, 1)
        
        layout.addLayout(inventory_cards_layout)

        # Lista de alertas de stock crítico
        alerts_label = QLabel("⚠️ Alertas de Stock Crítico")
        alerts_label.setObjectName("DashboardSectionTitle")
        layout.addWidget(alerts_label)

        self.alerts_table = QTableWidget()
        self.alerts_table.setObjectName("AlertsTable")
        self.alerts_table.setColumnCount(3)
        self.alerts_table.setHorizontalHeaderLabels(["Artículo", "Stock Actual", "Estado"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.alerts_table.setAlternatingRowColors(True)
        layout.addWidget(self.alerts_table)

        # Cargar métricas del dashboard
        self.load_dashboard_metrics()

        return tab

    def add_metric(self, layout, key, label, value, row, column):
        """Agrega una tarjeta de métrica al layout especificado."""
        card = QFrame()
        card.setObjectName("MetricCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        caption = QLabel(label)
        caption.setObjectName("MetricCaption")
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        card_layout.addWidget(caption)
        card_layout.addWidget(value_label)
        self.inventory_metric_values[key] = value_label
        layout.addWidget(card, row, column)

    def load_dashboard_metrics(self):
        """Carga las métricas del Dashboard de Inventario."""
        try:
            inventory = get_inventory_summary()
            
            # Valor total del inventario en CUP
            inventory_value_cup = sum(
                float(row.get("stock_a1", 0)) * float(row.get("precio_ponderado", 0))
                for row in inventory
            )
            
            # Valor total del inventario en USD
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT AVG(tasa_cambio) FROM ventas WHERE fecha_operacion LIKE ?",
                (f"{date.today().strftime('%Y-%m')}%",)
            )
            row_res = cursor.fetchone()
            avg_rate = float(row_res[0] if row_res and row_res[0] else 300)
            conn.close()
            
            inventory_value_usd = inventory_value_cup / avg_rate if avg_rate > 0 else 0
            
            # Total de artículos en Stock A1
            total_stock_a1 = sum(int(row.get("stock_a1", 0)) for row in inventory)
            
            # Artículos en tránsito
            in_transit = sum(int(row.get("en_transito", 0)) for row in inventory)
            
            # Alertas de stock crítico
            low_stock_products = [
                row for row in inventory 
                if int(row.get("stock_a1", 0)) < 3
            ]
            
            # Actualizar métricas de inventario
            self.inventory_metric_values["inventory_value_cup"].setText(format_money(inventory_value_cup, "CUP"))
            self.inventory_metric_values["inventory_value_usd"].setText(format_money(inventory_value_usd, "USD"))
            self.inventory_metric_values["total_stock_a1"].setText(str(total_stock_a1))
            self.inventory_metric_values["in_transit"].setText(str(in_transit))
            
            # Actualizar tabla de alertas
            self.alerts_table.setRowCount(len(low_stock_products))
            for row_idx, product in enumerate(low_stock_products):
                nombre = str(product.get("nombre", "Desconocido"))
                stock = int(product.get("stock_a1", 0))
                
                estado = "🔴 CRÍTICO" if stock == 0 else "🟡 BAJO"
                
                self.alerts_table.setItem(row_idx, 0, QTableWidgetItem(nombre))
                self.alerts_table.setItem(row_idx, 1, QTableWidgetItem(str(stock)))
                
                estado_item = QTableWidgetItem(estado)
                if stock == 0:
                    estado_item.setForeground(Qt.red)
                else:
                    estado_item.setForeground(Qt.darkYellow)
                self.alerts_table.setItem(row_idx, 2, estado_item)
                
        except Exception as e:
            print(f"Error cargando métricas de inventario: {e}")

    def load_data(self, fecha_inicio=None, fecha_fin=None):
        """Carga los datos ejecutando la consulta SQL del core."""
        data = get_inventory_summary(fecha_inicio, fecha_fin)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))

        for row_idx, row_data in enumerate(data):
            articulo_id = int(row_data.get('id', 0))
            nombre = str(row_data.get('nombre', '')).strip() or 'Artículo sin nombre'
            categoria = str(row_data.get('categoria', 'General')).strip() or 'General'
            peso = float(row_data.get('peso_lb', 0.0) or 0.0)
            precio_pond = float(row_data.get('precio_ponderado', 0.0) or 0.0)
            prec_pesaje_pond = peso * precio_pond
            stock_a1 = int(row_data.get('stock_a1', 0) or 0)
            stock_transito = int(row_data.get('total_transito', 0) or 0)
            inventario = int(row_data.get('inventario', 0) or 0)
            descripcion = str(row_data.get('descripcion', '')).strip() or 'Sin descripción'

            # Tooltip con la información completa
            tooltip_html = f"""
                <b>📦 Detalles del Artículo</b><br>
                • <b>Categoría:</b> {categoria}<br>
                • <b>Pesaje:</b> {format_custom_number(peso)} lb/u<br>
                • <b>Precio Costo Base:</b> {format_money(precio_pond)}<br>
                • <b>Descripción / Notas:</b> {descripcion}
            """

            # Columna 0: Nombre (Guardamos ID, Categoria, Peso y Descripcion en UserRole para la ventana modal)
            item_nombre = QTableWidgetItem(nombre)
            item_nombre.setData(Qt.UserRole, {
                "id": articulo_id,
                "categoria": categoria,
                "peso": peso,
                "descripcion": descripcion
            })
            item_nombre.setToolTip(tooltip_html)
            self.table.setItem(row_idx, 0, item_nombre)
            
            # Columna 1: Precio Ponderado
            item_precio_pond = QTableWidgetItem(format_money(precio_pond))
            item_precio_pond.setToolTip(tooltip_html)
            self.table.setItem(row_idx, 1, item_precio_pond)
            
            # Columna 2: Prec. Pesaje Pond.
            item_prec_pesaje = QTableWidgetItem(format_money(prec_pesaje_pond))
            item_prec_pesaje.setToolTip(tooltip_html)
            self.table.setItem(row_idx, 2, item_prec_pesaje)

            # Columna 3: Stock A1
            item_stock = QTableWidgetItem(str(stock_a1))
            item_stock.setToolTip(tooltip_html)
            if stock_a1 < 3:
                item_stock.setForeground(Qt.red)
            self.table.setItem(row_idx, 3, item_stock)

            # Columna 4: Stock en Tránsito
            item_transito = QTableWidgetItem(str(stock_transito))
            item_transito.setToolTip(tooltip_html)
            if stock_transito > 0:
                item_transito.setForeground(Qt.yellow)
            self.table.setItem(row_idx, 4, item_transito)

            # Columna 5: Inventario
            item_inventario = QTableWidgetItem(str(inventario))
            item_inventario.setToolTip(tooltip_html)
            self.table.setItem(row_idx, 5, item_inventario)

        self.table.setSortingEnabled(True)
        self.configure_table_sorting(self.table)
        self.load_dashboard_metrics()

    def check_system_date_coherence(self):
        """Verifica la coherencia de fecha entre el sistema y la DB."""
        hoy = date.today()
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT MAX(fecha) as max_fecha FROM compras")
            result = cursor.fetchone()
            max_fecha_compras = result['max_fecha'] if result and result['max_fecha'] else None
            
            cursor.execute("SELECT MAX(fecha) as max_fecha FROM envios")
            result = cursor.fetchone()
            max_fecha_envios = result['max_fecha'] if result and result['max_fecha'] else None
            
            fechas_db = []
            if max_fecha_compras:
                fechas_db.append(datetime.strptime(max_fecha_compras, "%Y-%m-%d").date())
            if max_fecha_envios:
                fechas_db.append(datetime.strptime(max_fecha_envios, "%Y-%m-%d").date())
            
            if fechas_db:
                max_fecha_db = max(fechas_db)
                diferencia = (hoy - max_fecha_db).days
                
                if diferencia < -1:
                    dias_retraso = abs(diferencia)
                    QMessageBox.warning(
                        self,
                        "⚠️ Incoherencia de Fecha del Sistema",
                        f"La fecha del sistema ({hoy.strftime('%d/%m/%Y')}) es ANTERIOR a los datos registrados en la DB.\n\n"
                        f"Fecha más reciente en DB: {max_fecha_db.strftime('%d/%m/%Y')}\n"
                        f"El sistema está {dias_retraso} días detrás.\n\n"
                        f"Por favor, verifique la fecha y hora del sistema."
                    )
        except Exception as e:
            print(f"Error al verificar coherencia de fecha: {e}")
        finally:
            conn.close()

    def on_double_click(self, item):
        """Maneja el evento de doble clic alineado a las 6 columnas actuales."""
        row = item.row()
        item_nombre = self.table.item(row, 0)
        if not item_nombre:
            QMessageBox.warning(self, "Error", "Artículo no válido")
            return

        extra_data = item_nombre.data(Qt.UserRole)
        if not extra_data or not isinstance(extra_data, dict):
            QMessageBox.warning(self, "Error", "No se pudo identificar los detalles del artículo")
            return

        nombre = item_nombre.text()
        categoria = extra_data.get("categoria", "-")
        peso = format_custom_number(extra_data.get("peso", 0.0))
        
        precio_pond = self.table.item(row, 1).text() if self.table.item(row, 1) else "-"
        prec_pesaje_pond = self.table.item(row, 2).text() if self.table.item(row, 2) else "-"
        stock_a1 = self.table.item(row, 3).text() if self.table.item(row, 3) else "-"
        transito = self.table.item(row, 4).text() if self.table.item(row, 4) else "-"
        inventario = self.table.item(row, 5).text() if self.table.item(row, 5) else "-"
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Detalle del Artículo: {nombre}")
        dialog.setMinimumWidth(450)
        
        form_layout = QFormLayout()
        form_layout.addRow("Artículo:", QLabel(nombre))
        form_layout.addRow("Categoría:", QLabel(categoria))
        form_layout.addRow("Pesaje lb/u:", QLabel(f"{peso} lb/u"))
        form_layout.addRow("Precio Ponderado:", QLabel(precio_pond))
        form_layout.addRow("Prec. Pesaje Pond.:", QLabel(prec_pesaje_pond))
        form_layout.addRow("Stock A1 (Actual):", QLabel(stock_a1))
        form_layout.addRow("Stock en Tránsito:", QLabel(transito))
        form_layout.addRow("Inventario disponible:", QLabel(inventario))
        
        info_label = QLabel("Este módulo es de consulta principal.\nPara modificar o transaccionar, use Compras o Envíos.")
        info_label.setObjectName("InventoryInfo")
        
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btn_cancelar")
        btn_cerrar.clicked.connect(dialog.accept)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(info_label)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cerrar)
        main_layout.addLayout(btn_layout)
        
        dialog.exec()