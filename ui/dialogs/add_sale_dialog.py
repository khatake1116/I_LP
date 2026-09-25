# ui/dialogs/add_sale_dialog.py
from datetime import date

from PySide6.QtCore import QDate, Signal, Qt, QRegularExpression
from PySide6.QtGui import QDoubleValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, 
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, 
    QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from core.formatting import format_money
from core.paths import get_app_config
from database.models import (
    get_articulos_disponibles, get_costo_total_articulo, 
    get_inventario_disponible, registrar_venta
)


class AddSaleDialog(QDialog):
    sale_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar Venta")
        self.setMinimumWidth(560)
        self.article_ids = {}
        self.config = get_app_config()
        self.costo_total_articulo = 0.0

        self.setup_ui()
        self.load_articles()
        self.update_totals()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # -------------------------------------------------------------
        # Grupo 1: Información de la Venta
        # -------------------------------------------------------------
        group_info = QGroupBox("Detalles de la Operación")
        group_info_layout = QGridLayout(group_info)
        group_info_layout.setSpacing(10)

        self.operation_date = QDateEdit(QDate.currentDate())
        self.operation_date.setCalendarPopup(True)
        self.operation_date.setDisplayFormat("dd/MM/yyyy")

        self.article_combo = QComboBox()
        self.article_combo.currentIndexChanged.connect(self.update_stock_label)
        self.article_combo.currentIndexChanged.connect(self.update_costo_total)

        self.stock_label = QLabel("Stock: -")
        self.stock_label.setStyleSheet("font-weight: bold; color: #555;")

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0.01, 999999999)
        self.quantity_input.setDecimals(2)
        self.quantity_input.setValue(1.0)
        self.quantity_input.valueChanged.connect(self.update_totals)

        self.price_input = QLineEdit()
        self.price_input.setValidator(QDoubleValidator(0, 999999999, 4, self))
        self.price_input.setPlaceholderText("0.00")
        self.price_input.textChanged.connect(self.update_totals)

        group_info_layout.addWidget(QLabel("Fecha:"), 0, 0)
        group_info_layout.addWidget(self.operation_date, 0, 1)
        group_info_layout.addWidget(QLabel("Artículo:"), 1, 0)
        group_info_layout.addWidget(self.article_combo, 1, 1, 1, 2)
        group_info_layout.addWidget(QLabel("Cantidad:"), 2, 0)

        # Sub-layout para cantidad y stock en la misma fila
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(self.quantity_input, 2)
        qty_layout.addWidget(self.stock_label, 1, Qt.AlignRight | Qt.AlignVCenter)
        group_info_layout.addLayout(qty_layout, 2, 1, 1, 2)

        group_info_layout.addWidget(QLabel("Precio Unitario:"), 3, 0)
        group_info_layout.addWidget(self.price_input, 3, 1, 1, 2)

        main_layout.addWidget(group_info)

        # -------------------------------------------------------------
        # Grupo 2: Moneda y Forma de Pago
        # -------------------------------------------------------------
        group_payment = QGroupBox("Cobro y Pago")
        payment_layout = QGridLayout(group_payment)
        payment_layout.setSpacing(10)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "CUP"])
        self.currency_combo.setCurrentText(self.config.get("moneda", "CUP"))
        self.currency_combo.currentTextChanged.connect(self.update_totals)

        self.rate_input = QLineEdit()
        self.rate_input.setValidator(QDoubleValidator(0.0001, 999999999, 4, self))
        self.rate_input.setText(str(self.config.get("tasa_cambio", 1.0)))
        self.rate_input.textChanged.connect(self.update_totals)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems([
            "Efectivo CUP",
            "Transferencia CUP (Pago en Línea / Transfermóvil)",
            "Efectivo USD",
            "Zelle / Transferencia USD"
        ])
        self.payment_combo.currentTextChanged.connect(self.on_payment_method_changed)

        self.transaction_input = QLineEdit()
        self.transaction_input.setPlaceholderText("N° DE TRANSACCIÓN / REFERENCIA")
        regex = QRegularExpression("[A-Z0-9]+")
        self.transaction_input.setValidator(QRegularExpressionValidator(regex, self))
        self.transaction_input.setVisible(False)

        payment_layout.addWidget(QLabel("Moneda:"), 0, 0)
        payment_layout.addWidget(self.currency_combo, 0, 1)
        payment_layout.addWidget(QLabel("Tasa de Cambio:"), 0, 2)
        payment_layout.addWidget(self.rate_input, 0, 3)

        payment_layout.addWidget(QLabel("Método de Pago:"), 1, 0)
        payment_layout.addWidget(self.payment_combo, 1, 1, 1, 3)

        self.lbl_transaction = QLabel("Ref. Transacción:")
        self.lbl_transaction.setVisible(False)
        payment_layout.addWidget(self.lbl_transaction, 2, 0)
        payment_layout.addWidget(self.transaction_input, 2, 1, 1, 3)

        main_layout.addWidget(group_payment)

        # -------------------------------------------------------------
        # Grupo 3: Resumen de Totales y Margen
        # -------------------------------------------------------------
        summary_card = QFrame()
        summary_card.setObjectName("PosSummaryBlock")
        summary_card.setStyleSheet(
            "QFrame#PosSummaryBlock { "
            "  border: 1px solid #E0E0E0; "
            "  border-radius: 8px; "
            "  background-color: #FAFAFA; "
            "}"
        )
        summary_layout = QGridLayout(summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(8)

        self.total_origin_label = QLabel("0.00 CUP")
        self.total_cup_label = QLabel("0.00 CUP")
        self.costo_total_label = QLabel("0.00 CUP")
        self.ganancia_neta_label = QLabel("0.00 CUP")
        self.margen_label = QLabel("0.00%")

        # Estilizado de textos del resumen
        for lbl in (self.total_origin_label, self.total_cup_label, self.costo_total_label, self.ganancia_neta_label, self.margen_label):
            lbl.setStyleSheet("font-weight: bold; font-size: 13px;")

        summary_layout.addWidget(QLabel("Total Origen:"), 0, 0)
        summary_layout.addWidget(self.total_origin_label, 0, 1, Qt.AlignRight)
        summary_layout.addWidget(QLabel("Total CUP:"), 0, 2)
        summary_layout.addWidget(self.total_cup_label, 0, 3, Qt.AlignRight)

        # Separador visual
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        summary_layout.addWidget(line, 1, 0, 1, 4)

        summary_layout.addWidget(QLabel("Costo Total:"), 2, 0)
        summary_layout.addWidget(self.costo_total_label, 2, 1, Qt.AlignRight)
        summary_layout.addWidget(QLabel("Ganancia Neta:"), 2, 2)
        summary_layout.addWidget(self.ganancia_neta_label, 2, 3, Qt.AlignRight)

        summary_layout.addWidget(QLabel("Margen:"), 3, 2)
        summary_layout.addWidget(self.margen_label, 3, 3, Qt.AlignRight)

        main_layout.addWidget(summary_card)

        # -------------------------------------------------------------
        # Botones de Acción
        # -------------------------------------------------------------
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        btn_cancelar.clicked.connect(self.reject)

        btn_guardar = QPushButton("Guardar Venta")
        btn_guardar.setObjectName("btn_primario")
        btn_guardar.setDefault(True)
        btn_guardar.clicked.connect(self.save_sale)

        button_layout.addWidget(btn_cancelar)
        button_layout.addWidget(btn_guardar)
        main_layout.addLayout(button_layout)

    def load_articles(self):
        self.article_combo.clear()
        self.article_ids.clear()
        for article in get_articulos_disponibles():
            article_id = article["id"]
            stock = get_inventario_disponible(article_id)
            if stock > 0:
                self.article_ids[self.article_combo.count()] = article_id
                self.article_combo.addItem(f"{article['nombre']} ({stock:g} dispo.)")
        self.update_stock_label()
        self.update_costo_total()

    def selected_article_id(self):
        return self.article_ids.get(self.article_combo.currentIndex())

    def update_stock_label(self):
        article_id = self.selected_article_id()
        stock = get_inventario_disponible(article_id) if article_id else 0
        max_quantity = max(1.0, float(stock) if stock > 0 else 0.01)
        self.quantity_input.setRange(0.01, max_quantity if stock > 0 else 0.01)
        
        if stock <= 0:
            self.quantity_input.setValue(0.01)
            self.quantity_input.setEnabled(False)
        else:
            self.quantity_input.setEnabled(True)
            if self.quantity_input.value() > max_quantity:
                self.quantity_input.setValue(max_quantity)
        
        self.stock_label.setText(f"Stock: {stock:g}")

    def update_costo_total(self):
        article_id = self.selected_article_id()
        self.costo_total_articulo = get_costo_total_articulo(article_id) if article_id else 0.0
        self.update_totals()

    def on_payment_method_changed(self, method):
        is_transfer = "Transferencia" in method or "Zelle" in method
        self.lbl_transaction.setVisible(is_transfer)
        self.transaction_input.setVisible(is_transfer)
        if is_transfer:
            self.transaction_input.setFocus()

    @staticmethod
    def numeric_value(field):
        text = field.text().strip().replace(",", ".")
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    def update_totals(self):
        total_origin = self.numeric_value(self.price_input) * self.quantity_input.value()
        rate = self.numeric_value(self.rate_input)
        currency = self.currency_combo.currentText()
        total_cup = total_origin if currency == "CUP" else total_origin * rate

        self.total_origin_label.setText(format_money(total_origin, currency))
        self.total_cup_label.setText(format_money(total_cup, "CUP"))

        # Cálculo de margen
        costo_total = self.costo_total_articulo * self.quantity_input.value()
        ganancia_neta = total_cup - costo_total
        margen_porcentaje = (ganancia_neta / total_cup * 100) if total_cup > 0 else 0.0

        self.costo_total_label.setText(format_money(costo_total, "CUP"))
        self.ganancia_neta_label.setText(format_money(ganancia_neta, "CUP"))
        self.margen_label.setText(f"{margen_porcentaje:.2f}%")

        if margen_porcentaje > 0:
            self.margen_label.setStyleSheet("color: #2E7D32; font-weight: bold; font-size: 13px;")
            self.ganancia_neta_label.setStyleSheet("color: #2E7D32; font-weight: bold; font-size: 13px;")
        else:
            self.margen_label.setStyleSheet("color: #C62828; font-weight: bold; font-size: 13px;")
            self.ganancia_neta_label.setStyleSheet("color: #C62828; font-weight: bold; font-size: 13px;")

    def save_sale(self):
        article_id = self.selected_article_id()
        price = self.numeric_value(self.price_input)
        rate = self.numeric_value(self.rate_input)
        quantity = self.quantity_input.value()
        currency = self.currency_combo.currentText()
        available_stock = get_inventario_disponible(article_id) if article_id else 0
        total_origin = price * quantity
        total_cup = total_origin if currency == "CUP" else total_origin * rate
        payment_method = self.payment_combo.currentText()
        
        is_transfer = "Transferencia" in payment_method or "Zelle" in payment_method
        if is_transfer and not self.transaction_input.text().strip():
            QMessageBox.warning(self, "Dato requerido", "Ingresa el N° de transacción/referencia.")
            return

        numero_transaccion = self.transaction_input.text().strip().upper() if is_transfer else None

        costo_total = self.costo_total_articulo * quantity
        ganancia_neta = total_cup - costo_total
        margen_porcentaje = (ganancia_neta / total_cup * 100) if total_cup > 0 else 0.0

        if not article_id or price <= 0 or rate <= 0:
            QMessageBox.warning(self, "Datos incompletos", "Selecciona un artículo e indica precio y tasa válidos.")
            return
        if quantity <= 0:
            QMessageBox.warning(self, "Cantidad inválida", "La cantidad debe ser mayor que cero.")
            return
        if quantity > available_stock:
            QMessageBox.warning(self, "Stock insuficiente", f"La venta supera el stock disponible ({available_stock:g}).")
            return

        ok, message, _ = registrar_venta(
            self.operation_date.date().toString("yyyy-MM-dd"), article_id, quantity,
            price, currency, rate, total_origin, total_cup,
            payment_method, self.config.get("sucursal", "Principal"),
            numero_transaccion, self.costo_total_articulo, 
            (self.costo_total_articulo * quantity) / quantity if quantity > 0 else 0.0, 
            margen_porcentaje
        )
        if not ok:
            QMessageBox.warning(self, "Error", message)
            self.load_articles()
            return
            
        self.sale_saved.emit()
        self.accept()
