# ui/views/dashboard_view.py
from datetime import date, datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, 
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView
)

from database.connection import get_connection
from core.formatting import format_money
from ui.views.base_view import BaseRefreshView


class DashboardView(BaseRefreshView):
    """Panel comercial con indicadores operativos de ventas."""

    def __init__(self):
        super().__init__()
        self.currency = "CUP"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        title = QLabel("Resumen del Negocio")
        title.setObjectName("DashboardTitle")
        subtitle = QLabel("Indicadores operativos y financieros de la sucursal")
        subtitle.setObjectName("DashboardSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Tarjetas KPI de Ventas
        sales_cards_layout = QGridLayout()
        sales_cards_layout.setSpacing(12)
        self.sales_metric_values = {}
        
        self.add_metric(sales_cards_layout, "total_cup", "Total Vendido en CUP", "0.00 CUP", 0, 0)
        self.add_metric(sales_cards_layout, "total_usd", "Total Vendido en USD", "0.00 USD", 0, 1)
        self.add_metric(sales_cards_layout, "ganancia_neta", "Ganancia Neta Acumulada", "0.00 CUP", 0, 2)
        self.add_metric(sales_cards_layout, "transfer_vs_cash", "Ventas Transferencia vs Efectivo", "0% / 0%", 1, 0)
        
        layout.addLayout(sales_cards_layout)

        # Tabla de artículos más vendidos
        top_products_label = QLabel("📊 Top 5 Artículos Más Vendidos")
        top_products_label.setObjectName("DashboardSectionTitle")
        layout.addWidget(top_products_label)

        self.top_products_table = QTableWidget()
        self.top_products_table.setColumnCount(3)
        self.top_products_table.setHorizontalHeaderLabels(["Artículo", "Cantidad Vendida", "Total CUP"])
        self.top_products_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.top_products_table.verticalHeader().setVisible(False)
        self.top_products_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.top_products_table.setAlternatingRowColors(True)
        layout.addWidget(self.top_products_table)

        footer = QFrame()
        footer.setObjectName("DashboardFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        footer_layout.addStretch()
        self.clock_label = QLabel()
        self.clock_label.setObjectName("DashboardClock")
        footer_layout.addWidget(self.clock_label)
        layout.addWidget(footer)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()
        self.load_metrics()

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
        self.sales_metric_values[key] = value_label
        layout.addWidget(card, row, column)

    def load_data(self):
        self.load_metrics()

    def load_metrics(self):
        """Carga todas las métricas de ventas."""
        try:
            self.load_sales_metrics()
        except Exception as e:
            print(f"Error cargando métricas: {e}")

    def load_sales_metrics(self):
        """Carga las métricas del Dashboard de Ventas."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            month = date.today().strftime("%Y-%m")
            
            # Total vendido en CUP
            cursor.execute(
                "SELECT COALESCE(SUM(total_cup), 0) FROM ventas "
                "WHERE fecha_operacion LIKE ?", (f"{month}%",)
            )
            total_cup = float(cursor.fetchone()[0] or 0)
            
            # Total vendido en USD (convertido)
            cursor.execute(
                "SELECT COALESCE(SUM(total_origen), 0) FROM ventas "
                "WHERE fecha_operacion LIKE ? AND moneda = 'USD'", (f"{month}%",)
            )
            total_usd = float(cursor.fetchone()[0] or 0)
            
            # Ganancia neta acumulada (controlando valores NULL en los costos)
            cursor.execute(
                "SELECT COALESCE(SUM(COALESCE(total_cup, 0) - (COALESCE(costo_articulo, 0) + COALESCE(costo_logistico, 0)) * COALESCE(cantidad, 0)), 0) "
                "FROM ventas WHERE fecha_operacion LIKE ?", (f"{month}%",)
            )
            ganancia_neta = float(cursor.fetchone()[0] or 0)
            
            # Ventas por transferencia vs efectivo
            cursor.execute(
                "SELECT metodo_pago, COALESCE(SUM(total_cup), 0) FROM ventas "
                "WHERE fecha_operacion LIKE ? GROUP BY metodo_pago", (f"{month}%",)
            )
            payment_methods = cursor.fetchall()
            
            transfer_total = sum(float(row[1] or 0) for row in payment_methods if row[0] and ("Transferencia" in row[0] or "Zelle" in row[0]))
            cash_total = sum(float(row[1] or 0) for row in payment_methods if row[0] and "Efectivo" in row[0])
            total_payments = transfer_total + cash_total
            
            if total_payments > 0:
                transfer_pct = (transfer_total / total_payments) * 100
                cash_pct = (cash_total / total_payments) * 100
            else:
                transfer_pct = cash_pct = 0.0

            # Top 5 artículos más vendidos
            cursor.execute(
                """
                SELECT a.nombre, SUM(v.cantidad) as total_cantidad, SUM(v.total_cup) as total_cup
                FROM ventas v
                LEFT JOIN articulos a ON a.id = v.articulo_id
                WHERE v.fecha_operacion LIKE ?
                GROUP BY v.articulo_id, a.nombre
                ORDER BY total_cantidad DESC
                LIMIT 5
                """, (f"{month}%",)
            )
            top_products = cursor.fetchall()
            
            # Actualizar métricas de ventas
            self.sales_metric_values["total_cup"].setText(format_money(total_cup, "CUP"))
            self.sales_metric_values["total_usd"].setText(format_money(total_usd, "USD"))
            self.sales_metric_values["ganancia_neta"].setText(format_money(ganancia_neta, "CUP"))
            self.sales_metric_values["transfer_vs_cash"].setText(f"{transfer_pct:.1f}% / {cash_pct:.1f}%")
            
            # Actualizar tabla de productos más vendidos
            self.top_products_table.setRowCount(len(top_products))
            for row_idx, product in enumerate(top_products):
                nombre = str(product[0]) if product[0] else "Artículo no encontrado"
                cantidad = f"{float(product[1] or 0):g}"
                total = format_money(float(product[2] or 0), "CUP")
                
                self.top_products_table.setItem(row_idx, 0, QTableWidgetItem(nombre))
                self.top_products_table.setItem(row_idx, 1, QTableWidgetItem(cantidad))
                self.top_products_table.setItem(row_idx, 2, QTableWidgetItem(total))
                
        except Exception as e:
            print(f"Error cargando métricas de ventas: {e}")
        finally:
            if conn:
                conn.close()

    def set_currency(self, currency):
        self.currency = currency
        self.load_metrics()

    def update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%d/%m/%Y  •  %H:%M:%S"))