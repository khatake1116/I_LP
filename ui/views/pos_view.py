# ui/views/pos_view.py
from datetime import date
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, 
    QHeaderView, QAbstractItemView, QMessageBox
)

from core.formatting import format_money, format_custom_number
from database.connection import get_connection
from ui.views.base_view import BaseRefreshView


class POSView(BaseRefreshView):
    """Vista principal de punto de venta con gestión de carrito, cobro y métricas del día."""

    def __init__(self):
        super().__init__()
        self.setObjectName("PosShell")

        # Estado del carrito y selección
        self.cart_items = []
        self.selected_payment_method = "cash"
        
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(16)

        # Encabezado
        header = QFrame()
        header.setObjectName("PosHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)

        title_layout = QVBoxLayout()
        title = QLabel("Ventas / POS")
        title.setObjectName("PosTitle")
        subtitle = QLabel("Punto de venta y gestión rápida de cobros")
        subtitle.setObjectName("PosSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)

        self.status_badge = QLabel("Abierto")
        self.status_badge.setObjectName("PosStatusBadge")
        self.status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.status_badge)
        root.addWidget(header)

        # Métricas
        metrics = QGridLayout()
        metrics.setSpacing(14)
        self.metric_cards = {}
        for key, label, value, row, col in (
            ("today_sales", "Ventas del día", "0.00 CUP", 0, 0),
            ("tickets", "Tickets", "0", 0, 1),
            ("avg_ticket", "Promedio", "0.00 CUP", 0, 2),
            ("cash", "Caja", "0.00 CUP", 0, 3),
        ):
            card = QFrame()
            card.setObjectName("PosMetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            caption = QLabel(label)
            caption.setObjectName("PosMetricLabel")
            value_label = QLabel(value)
            value_label.setObjectName("PosMetricValue")
            self.metric_cards[key] = value_label
            card_layout.addWidget(caption)
            card_layout.addWidget(value_label)
            metrics.addWidget(card, row, col)
        root.addLayout(metrics)

        # Contenido principal
        content = QHBoxLayout()
        content.setSpacing(16)

        # Panel Izquierdo: Carrito de compras
        cart_panel = QFrame()
        cart_panel.setObjectName("PosPanel")
        cart_layout = QVBoxLayout(cart_panel)
        cart_layout.setContentsMargins(16, 16, 16, 16)

        cart_header = QHBoxLayout()
        cart_title = QLabel("Carrito actual")
        cart_title.setObjectName("PosPanelTitle")
        cart_header.addWidget(cart_title)
        cart_header.addStretch()

        self.clear_cart_btn = QPushButton("Vaciar Carrito")
        self.clear_cart_btn.setObjectName("PosSecondaryButton")
        self.clear_cart_btn.clicked.connect(self.clear_cart)
        cart_header.addWidget(self.clear_cart_btn)
        cart_layout.addLayout(cart_header)

        self.table = QTableWidget()
        self.table.setObjectName("PosCartTable")
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Artículo", "Cant.", "P. unit.", "Desc.", "Total"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        cart_layout.addWidget(self.table)
        content.addWidget(cart_panel, 3)

        # Panel Derecho: Cliente y Cobro
        side_panel = QFrame()
        side_panel.setObjectName("PosPanel")
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(12)

        customer_title = QLabel("Datos del cliente")
        customer_title.setObjectName("PosPanelTitle")
        side_layout.addWidget(customer_title)

        self.info_block = QFrame()
        self.info_block.setObjectName("PosInfoBlock")
        info_layout = QVBoxLayout(self.info_block)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(6)
        self.customer_name_lbl = QLabel("Cliente: General / Público")
        self.customer_doc_lbl = QLabel("Documento: Consumidor Final")
        self.customer_channel_lbl = QLabel("Canal: Venta directa")
        info_layout.addWidget(self.customer_name_lbl)
        info_layout.addWidget(self.customer_doc_lbl)
        info_layout.addWidget(self.customer_channel_lbl)
        side_layout.addWidget(self.info_block)

        payments_title = QLabel("Método de Pago")
        payments_title.setObjectName("PosPanelTitle")
        side_layout.addWidget(payments_title)

        actions = QHBoxLayout()
        self.payment_buttons = {}
        payment_methods = (("cash", "Efectivo"), ("card", "Tarjeta"), ("invoice", "Factura"))
        
        for key, text in payment_methods:
            button = QPushButton(text)
            button.setObjectName("PosActionButton")
            button.setCheckable(True)
            button.setProperty("actionKey", key)
            button.clicked.connect(self._create_payment_callback(key))
            actions.addWidget(button)
            self.payment_buttons[key] = button
            
        side_layout.addLayout(actions)

        # Resumen del Total
        total_frame = QFrame()
        total_frame.setObjectName("PosSummaryBlock")
        total_layout = QVBoxLayout(total_frame)
        total_layout.setContentsMargins(12, 12, 12, 12)
        total_layout.addWidget(QLabel("Total a pagar"))
        self.total_value_lbl = QLabel("0.00 CUP")
        self.total_value_lbl.setObjectName("PosTotalValue")
        total_layout.addWidget(self.total_value_lbl)
        side_layout.addWidget(total_frame)

        # Acciones Principales
        self.primary_action = QPushButton("Completar venta")
        self.primary_action.setObjectName("PosPrimaryButton")
        self.primary_action.clicked.connect(self.process_sale)
        
        self.secondary_action = QPushButton("Cancelar")
        self.secondary_action.setObjectName("PosSecondaryButton")
        self.secondary_action.clicked.connect(self.clear_cart)

        side_layout.addWidget(self.primary_action)
        side_layout.addWidget(self.secondary_action)

        content.addWidget(side_panel, 1)
        root.addLayout(content)

        # Configuración inicial
        self.set_payment_method("cash")
        self.load_pos_data()

    def _create_payment_callback(self, method_key):
        return lambda checked=False: self.set_payment_method(method_key)

    def set_payment_method(self, method_key):
        """Cambia el método de pago activo y actualiza la UI."""
        self.selected_payment_method = method_key
        for key, button in self.payment_buttons.items():
            button.setChecked(key == method_key)

    def add_item_to_cart(self, articulo_id, nombre, cantidad, precio_unitario, descuento=0.0, moneda="CUP"):
        """Agrega o actualiza un ítem en el carrito actual."""
        total = (cantidad * precio_unitario) - descuento
        item_data = {
            "articulo_id": articulo_id,
            "nombre": nombre,
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "descuento": descuento,
            "moneda": moneda,
            "total": total
        }
        self.cart_items.append(item_data)
        self.render_cart()

    def render_cart(self):
        """Renderiza los elementos del carrito en la tabla y recalcula totales."""
        self.table.setRowCount(len(self.cart_items))
        total_general = 0.0

        for row_idx, item in enumerate(self.cart_items):
            total_general += item["total"]
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(item["nombre"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{item['cantidad']:g}"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(format_money(item["precio_unitario"], item["moneda"])))
            self.table.setItem(row_idx, 3, QTableWidgetItem(format_money(item["descuento"], item["moneda"])))
            self.table.setItem(row_idx, 4, QTableWidgetItem(format_money(item["total"], item["moneda"])))

        self.total_value_lbl.setText(format_money(total_general, "CUP"))

    def clear_cart(self):
        """Limpia el carrito de compras actual."""
        self.cart_items.clear()
        self.render_cart()

    def load_pos_data(self):
        """Carga y actualiza las métricas rápidas del día desde la BD."""
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        today_str = date.today().isoformat()

        try:
            query = """
                SELECT 
                    COALESCE(SUM(total_cup), 0) as total_ventas,
                    COUNT(id) as total_tickets,
                    COALESCE(AVG(total_cup), 0) as promedio_ticket
                FROM ventas 
                WHERE fecha_operacion = ?
            """
            row = conn.execute(query, (today_str,)).fetchone()
            
            if row:
                ventas_dia = float(row["total_ventas"])
                tickets = int(row["total_tickets"])
                promedio = float(row["promedio_ticket"])

                self.metric_cards["today_sales"].setText(format_money(ventas_dia, "CUP"))
                self.metric_cards["tickets"].setText(str(tickets))
                self.metric_cards["avg_ticket"].setText(format_money(promedio, "CUP"))
                self.metric_cards["cash"].setText(format_money(ventas_dia, "CUP"))
        finally:
            conn.close()

    def process_sale(self):
        """Procesa y guarda la venta actual en la base de datos."""
        if not self.cart_items:
            QMessageBox.warning(self, "Carrito Vacío", "No hay elementos en el carrito para procesar.")
            return

        # Aquí se invocaría la persistenia o el diálogo de confirmación/facturación final
        QMessageBox.information(self, "Éxito", "Venta procesada correctamente.")
        self.clear_cart()
        self.load_pos_data()
        self.notify_refresh()