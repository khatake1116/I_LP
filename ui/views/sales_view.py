# ui/views/sales_view.py
from datetime import date, timedelta
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QAbstractItemView, QMessageBox
)

from core.formatting import format_money, format_custom_number
from database.connection import get_connection
from database.models import delete_venta
from ui.dialogs.add_sale_dialog import AddSaleDialog
from ui.views.base_view import BaseRefreshView


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem personalizado para ordenar valores numéricos correctamente."""
    def __init__(self, display_text, sort_value):
        super().__init__(display_text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class SalesView(BaseRefreshView):
    """Registro contable y consulta de ventas con cálculo de margen real."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SalesShell")
        self.active_filter = "all"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("SalesHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)

        title = QLabel("Ventas")
        title.setObjectName("SalesHeaderTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.total_label = QLabel("0.00 CUP")
        self.total_label.setObjectName("SalesTotalValue")
        header_layout.addWidget(self.total_label)
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setObjectName("SalesToolbar")
        self.add_button = QPushButton("+ Registrar Venta")
        self.add_button.setObjectName("LogisticsPrimaryButton")
        self.add_button.clicked.connect(self.open_add_sale)
        toolbar.addWidget(self.add_button)
        toolbar.addStretch()
        
        self.filter_buttons = {}
        filters = (
            ("today", "Hoy"),
            ("yesterday", "Ayer"),
            ("week", "Semana"),
            ("month", "Mes"),
            ("all", "Todos"),
        )
        for key, text in filters:
            button = QPushButton(text)
            button.setObjectName("FilterButton")
            button.setCheckable(True)
            button.clicked.connect(self._create_filter_callback(key))
            self.filter_buttons[key] = button
            toolbar.addWidget(button)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setObjectName("SalesTable")
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Artículo", "Cant.", "Precio Venta", "Moneda", 
            "Tasa Cambio", "Total CUP", "Método Pago", "N° Transacción", "Margen (%)", "Acciones"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(QLabel("Total del filtro actual:"))
        self.total_filter_label = QLabel("0.00 CUP")
        self.total_filter_label.setObjectName("SalesFilterTotal")
        footer.addWidget(self.total_filter_label)
        layout.addLayout(footer)

        self.set_filter("all")

    def _create_filter_callback(self, key):
        return lambda checked=False: self.set_filter(key)

    def open_add_sale(self):
        dialog = AddSaleDialog(self)
        dialog.sale_saved.connect(self.load_sales)
        dialog.sale_saved.connect(self.notify_refresh)
        dialog.exec()

    def set_filter(self, filter_key):
        self.active_filter = filter_key
        for key, button in self.filter_buttons.items():
            button.setChecked(key == filter_key)
        self.load_sales()

    def date_range(self):
        today = date.today()
        if self.active_filter == "today":
            return today.isoformat(), today.isoformat()
        if self.active_filter == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday.isoformat(), yesterday.isoformat()
        if self.active_filter == "week":
            return (today - timedelta(days=today.weekday())).isoformat(), today.isoformat()
        if self.active_filter == "month":
            return today.replace(day=1).isoformat(), today.isoformat()
        return None, None

    def load_sales(self):
        start, end = self.date_range()
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Asegura acceso seguro por nombre de columna
        
        try:
            query = """
                SELECT v.id, v.fecha_operacion, a.nombre, v.cantidad, v.precio_unitario,
                       v.moneda, v.tasa_cambio, v.total_cup, v.metodo_pago, 
                       v.numero_transaccion, v.margen_ganancia
                FROM ventas v
                LEFT JOIN articulos a ON a.id = v.articulo_id
            """
            params = []
            if start and end:
                query += " WHERE v.fecha_operacion BETWEEN ? AND ?"
                params.extend([start, end])
            query += " ORDER BY v.fecha_operacion DESC, v.id DESC"
            
            rows = conn.execute(query, params).fetchall()
            
            sum_query = "SELECT COALESCE(SUM(total_cup), 0) FROM ventas"
            if start and end:
                sum_query += " WHERE fecha_operacion BETWEEN ? AND ?"
            
            total = conn.execute(sum_query, params if start and end else []).fetchone()[0]
        finally:
            conn.close()

        # Desactivar ordenamiento durante el dibujado de celdas
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            articulo_text = str(row["nombre"]) if row["nombre"] else "Artículo no encontrado"
            metodo_pago_text = str(row["metodo_pago"]) if row["metodo_pago"] else "No especificado"
            transaccion_text = str(row["numero_transaccion"]) if row["numero_transaccion"] else "-"
            margen = float(row["margen_ganancia"] or 0)
            cantidad = float(row["cantidad"] or 0)
            precio_unitario = float(row["precio_unitario"] or 0)
            tasa_cambio = float(row["tasa_cambio"] or 0)
            total_cup = float(row["total_cup"] or 0)

            # Celdas con ordenamiento nativo correcto
            item_fecha = QTableWidgetItem(str(row["fecha_operacion"] or ''))
            item_articulo = QTableWidgetItem(articulo_text)
            item_cant = NumericTableWidgetItem(f"{cantidad:g}", cantidad)
            item_precio = NumericTableWidgetItem(format_money(precio_unitario, row["moneda"]), precio_unitario)
            item_moneda = QTableWidgetItem(str(row["moneda"] or ''))
            item_tasa = NumericTableWidgetItem(format_money(tasa_cambio, "CUP"), tasa_cambio)
            item_total = NumericTableWidgetItem(format_money(total_cup, "CUP"), total_cup)
            item_metodo = QTableWidgetItem(metodo_pago_text)
            item_transaccion = QTableWidgetItem(transaccion_text)
            item_margen = NumericTableWidgetItem(f"{format_custom_number(margen)}%", margen)

            # Resaltado visual condicional para el margen
            if margen > 0:
                item_margen.setForeground(Qt.green)
            elif margen < 0:
                item_margen.setForeground(Qt.red)

            self.table.setItem(row_index, 0, item_fecha)
            self.table.setItem(row_index, 1, item_articulo)
            self.table.setItem(row_index, 2, item_cant)
            self.table.setItem(row_index, 3, item_precio)
            self.table.setItem(row_index, 4, item_moneda)
            self.table.setItem(row_index, 5, item_tasa)
            self.table.setItem(row_index, 6, item_total)
            self.table.setItem(row_index, 7, item_metodo)
            self.table.setItem(row_index, 8, item_transaccion)
            self.table.setItem(row_index, 9, item_margen)

            # Botón eliminar
            btn_delete = QPushButton("Eliminar")
            btn_delete.setObjectName("btn_danger")
            btn_delete.setFixedWidth(80)
            btn_delete.clicked.connect(self._create_delete_callback(row["id"]))
            self.table.setCellWidget(row_index, 10, btn_delete)

        # Reactivar ordenamiento tras poblar la tabla
        self.table.setSortingEnabled(True)

        self.total_label.setText(format_money(total, "CUP"))
        self.total_filter_label.setText(format_money(total, "CUP"))

    def _create_delete_callback(self, venta_id):
        return lambda checked=False: self.delete_sale(venta_id)

    def delete_sale(self, venta_id):
        """Elimina una venta específica."""
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            "¿Está seguro de eliminar esta venta? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_venta(venta_id):
                QMessageBox.information(self, "Éxito", "Venta eliminada correctamente.")
                self.load_sales()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar la venta.")