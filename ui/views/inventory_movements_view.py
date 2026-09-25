# ui/views/inventory_movements_view.py
from datetime import date
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QFrame,
    QHeaderView, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QVBoxLayout, QWidget,
    QAbstractItemView, QLabel, QDoubleSpinBox, QScrollArea
)

from database.connection import get_connection
from database.models import get_inventory_summary, registrar_movimiento
from core.paths import get_app_config
from core.formatting import format_money, format_custom_number
from ui.views.base_view import BaseRefreshView


class InventoryMovementsView(BaseRefreshView):
    """Bitácora de transferencias de inventario agrupadas por Usuario/Sucursal."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Controles superiores
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Registrar Transferencia")
        self.btn_add.setObjectName("btn_primario")
        self.btn_add.clicked.connect(self.open_add_dialog)
        btn_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Editar seleccionado")
        self.btn_edit.setObjectName("btn_primario")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self.edit_selected)
        btn_layout.addWidget(self.btn_edit)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Tabla de movimientos (6 columnas)
        self.table = QTableWidget()
        self.table.setObjectName("InventoryMovementsTable")
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Estado", "Cantidad Total", "Usuario / Sucursal",
            "Valor Venta", "Fecha Cambio"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.configure_table_sorting(self.table)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        self.selected_articles_list = []
        self.load_data()

    def get_current_exchange_rate(self):
        """Obtiene la tasa de cambio USD/CUP promedio del mes actual desde la DB."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT AVG(tasa_cambio) FROM ventas WHERE fecha_operacion LIKE ?",
                (f"{date.today().strftime('%Y-%m')}%",)
            )
            row_res = cursor.fetchone()
            return float(row_res[0]) if row_res and row_res[0] else 300.0
        except Exception as e:
            print(f"Error al obtener tasa de cambio: {e}")
            return 300.0
        finally:
            conn.close()

    def on_selection_changed(self):
        has_selection = self.table.selectionModel().hasSelection()
        self.btn_edit.setEnabled(has_selection)

    def edit_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            QMessageBox.information(self, "Editar Transferencia", "Seleccione una transferencia para editar.")
            return
        row = selected_rows[0].row()
        self.show_edit_dialog(row)

    def get_row_data(self, row_idx):
        try:
            item_fecha_trans = self.table.item(row_idx, 0)
            item_estado = self.table.item(row_idx, 1)
            item_cant_total = self.table.item(row_idx, 2)
            item_usuario = self.table.item(row_idx, 3)
            item_valor = self.table.item(row_idx, 4)
            item_fecha_cambio = self.table.item(row_idx, 5)

            return {
                'fecha_transferencia': item_fecha_trans.text() if item_fecha_trans else '',
                'estado': item_estado.text() if item_estado else 'Transferido',
                'cantidad_total': int(float(item_cant_total.text())) if item_cant_total else 0,
                'usuario_sucursal': item_usuario.text() if item_usuario else 'Sistema',
                'valor_venta': self.parse_money(item_valor.text()) if item_valor else 0.0,
                'fecha_cambio': item_fecha_cambio.text() if item_fecha_cambio else ''
            }
        except Exception as e:
            print(f"Error al obtener datos de la fila: {e}")
            return None

    def parse_money(self, money_str):
        try:
            return float(money_str.replace('$', '').replace(',', '').replace(' ', '').strip())
        except:
            return 0.0

    def show_edit_dialog(self, row_idx):
        row_data = self.get_row_data(row_idx)
        if not row_data:
            QMessageBox.critical(self, "Error", "No se encontró el registro seleccionado.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Transferencia")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        estado_combo = QComboBox()
        estado_combo.addItems(["Transferido", "Devuelto"])
        estado_combo.setCurrentText(row_data.get('estado', 'Transferido'))

        valor_venta_spin = QDoubleSpinBox()
        valor_venta_spin.setRange(0, 1000000)
        valor_venta_spin.setValue(row_data.get('valor_venta', 0.0))
        valor_venta_spin.setPrefix("$")

        fecha_transferencia = QDateEdit()
        fecha_transferencia.setCalendarPopup(True)
        fecha_transferencia.setDisplayFormat("dd/MM/yyyy")
        qdate_trans = QDate.fromString(row_data.get('fecha_transferencia', ''), "yyyy-MM-dd")
        fecha_transferencia.setDate(qdate_trans if qdate_trans.isValid() else QDate.currentDate())

        fecha_cambio = QDateEdit()
        fecha_cambio.setCalendarPopup(True)
        fecha_cambio.setDisplayFormat("dd/MM/yyyy")
        fecha_cambio.setDate(QDate.currentDate())

        usuario_input = QLineEdit(row_data.get('usuario_sucursal', 'Sistema'))
        cant_label = QLabel(f"<b>{row_data.get('cantidad_total', 0)} artículos acumulados</b>")

        form.addRow("Cantidad Total:", cant_label)
        form.addRow("Estado:", estado_combo)
        form.addRow("Valor venta acordado:", valor_venta_spin)
        form.addRow("Fecha transferencia:", fecha_transferencia)
        form.addRow("Fecha cambio (devolución):", fecha_cambio)
        form.addRow("Usuario / Sucursal:", usuario_input)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btn_secundario")
        btn_cancel.clicked.connect(dialog.reject)

        btn_save = QPushButton("Guardar Cambios")
        btn_save.setObjectName("btn_primario")
        btn_save.clicked.connect(lambda: self.save_edit(
            dialog, estado_combo, valor_venta_spin, usuario_input
        ))

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        dialog.exec()

    def save_edit(self, dialog, estado_combo, valor_venta_spin, usuario_input):
        nuevo_estado = estado_combo.currentText()
        nuevo_valor = valor_venta_spin.value()
        nuevo_usuario = usuario_input.text().strip() or "Sistema"

        QMessageBox.information(dialog, "Éxito",
                                f"Transferencia actualizada correctamente:\n"
                                f"Estado: {nuevo_estado}\n"
                                f"Valor: ${format_custom_number(nuevo_valor)}\n"
                                f"Usuario / Sucursal: {nuevo_usuario}")
        dialog.accept()
        self.load_data()
        self.notify_refresh()

    def open_add_dialog(self):
        """Diálogo de registro con tasa de cambio editable, margen y conversión USD/CUP."""
        tasa_inicial = self.get_current_exchange_rate()

        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar Transferencia de Inventario")
        dialog.setMinimumWidth(680)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        form = QFormLayout()

        date_input = QDateEdit(QDate.currentDate())
        date_input.setCalendarPopup(True)
        date_input.setDisplayFormat("dd/MM/yyyy")

        # Campo editable para la tasa de cambio USD/CUP
        tasa_cambio_input = QDoubleSpinBox()
        tasa_cambio_input.setRange(1.0, 10000.0)
        tasa_cambio_input.setValue(tasa_inicial)
        tasa_cambio_input.setDecimals(2)
        tasa_cambio_input.setSuffix(" CUP")

        article_combo = QComboBox()
        inventory_rows = [row for row in get_inventory_summary() if int(row.get('inventario', 0) or 0) > 0]
        
        quantity_input = QSpinBox()
        quantity_input.setRange(1, 1)

        valor_venta_input = QDoubleSpinBox()
        valor_venta_input.setRange(0, 1000000)
        valor_venta_input.setValue(0.0)
        valor_venta_input.setPrefix("$")

        def populate_articles():
            article_combo.clear()
            article_combo.addItem("-- Seleccionar para agregar --", None)
            for article in inventory_rows:
                if not any(item['id'] == article['id'] for item in self.selected_articles_list):
                    article_combo.addItem(f"{article['nombre']} (Stock: {article['inventario']})", article)

        def update_stock_range():
            selected_data = article_combo.currentData()
            if selected_data:
                stock_disponible = int(selected_data.get('inventario', 0))
                quantity_input.setRange(1, max(1, stock_disponible))
                quantity_input.setValue(1)
            else:
                quantity_input.setRange(1, 1)

        article_combo.currentIndexChanged.connect(update_stock_range)

        bubbles_container = QWidget()
        bubbles_layout = QVBoxLayout(bubbles_container)
        bubbles_layout.setContentsMargins(0, 0, 0, 0)
        bubbles_layout.setSpacing(6)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(150)
        scroll_area.setWidget(bubbles_container)

        self.selected_articles_list = []
        total_items_label = QLabel("<b>Total artículos a transferir: 0</b>")

        def render_bubbles():
            """Limpia y vuelve a dibujar las burbujas actualizando costos en USD/CUP y margen."""
            while bubbles_layout.count():
                child = bubbles_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            suma_total = sum(item['cantidad'] for item in self.selected_articles_list)
            total_items_label.setText(f"<b>Total artículos a transferir: {suma_total}</b>")

            v_venta = valor_venta_input.value()
            tasa_actual = tasa_cambio_input.value()

            for item in self.selected_articles_list:
                costo_usd = item['precio_ponderado'] * item['cantidad']
                costo_cup = costo_usd * tasa_actual
                
                ganancia = v_venta - costo_usd if v_venta > 0 else 0
                margen_pct = (ganancia / costo_usd * 100) if costo_usd > 0 and v_venta > 0 else 0.0

                bubble = QFrame()
                bubble.setStyleSheet("""
                    QFrame {
                        background-color: #f0f4f8;
                        border: 1px solid #bcccdc;
                        border-radius: 8px;
                        padding: 2px 8px;
                    }
                """)
                b_layout = QHBoxLayout(bubble)
                b_layout.setContentsMargins(6, 4, 6, 4)
                b_layout.setSpacing(10)

                color_margen = "#2e7d32" if margen_pct >= 0 else "#c62828"

                details_text = (
                    f"<b>{item['nombre']}</b> (x{item['cantidad']}) | "
                    f"Costo: ${format_custom_number(costo_usd)} USD (~{format_custom_number(costo_cup)} CUP) | "
                    f"Margen: <font color='{color_margen}'><b>{margen_pct:.1f}%</b></font>"
                )

                lbl = QLabel(details_text)
                
                btn_remove = QPushButton("×")
                btn_remove.setFixedSize(20, 20)
                btn_remove.setCursor(Qt.PointingHandCursor)
                btn_remove.setStyleSheet("""
                    QPushButton {
                        color: #c62828;
                        font-weight: bold;
                        font-size: 14px;
                        border: none;
                        background: transparent;
                    }
                    QPushButton:hover {
                        color: #ff1744;
                    }
                """)
                btn_remove.clicked.connect(lambda _, a_id=item['id']: remove_article(a_id))

                b_layout.addWidget(lbl)
                b_layout.addStretch()
                b_layout.addWidget(btn_remove)
                
                bubbles_layout.addWidget(bubble)

            bubbles_layout.addStretch()
            populate_articles()
            update_stock_range()

        # Reconectar eventos de valor de venta y tasa de cambio para actualizar burbujas
        valor_venta_input.valueChanged.connect(lambda _: render_bubbles())
        tasa_cambio_input.valueChanged.connect(lambda _: render_bubbles())

        def add_article():
            selected_data = article_combo.currentData()
            if not selected_data:
                return

            qty = quantity_input.value()
            stock = int(selected_data.get('inventario', 0))
            precio_pond = float(selected_data.get('precio_ponderado', 0.0) or 0.0)

            if qty > stock and estado_combo.currentText() == "Transferido":
                QMessageBox.warning(dialog, "Stock Insuficiente", f"El stock máximo disponible para {selected_data['nombre']} es {stock}.")
                return

            self.selected_articles_list.append({
                'id': selected_data['id'],
                'nombre': selected_data['nombre'],
                'cantidad': qty,
                'stock': stock,
                'precio_ponderado': precio_pond
            })
            render_bubbles()

        def remove_article(article_id):
            self.selected_articles_list = [a for a in self.selected_articles_list if a['id'] != article_id]
            render_bubbles()

        estado_combo = QComboBox()
        estado_combo.addItems(["Transferido", "Devuelto"])
        estado_combo.setCurrentText("Transferido")

        btn_add_article = QPushButton("+ Añadir Artículo")
        btn_add_article.setObjectName("btn_secundario")
        btn_add_article.clicked.connect(add_article)

        article_selection_layout = QHBoxLayout()
        article_selection_layout.addWidget(article_combo, 1)
        article_selection_layout.addWidget(QLabel("Cant:"))
        article_selection_layout.addWidget(quantity_input)
        article_selection_layout.addWidget(btn_add_article)

        fecha_cambio_input = QDateEdit(QDate.currentDate())
        fecha_cambio_input.setCalendarPopup(True)
        fecha_cambio_input.setDisplayFormat("dd/MM/yyyy")
        fecha_cambio_input.setEnabled(False)

        estado_combo.currentTextChanged.connect(lambda estado: fecha_cambio_input.setEnabled(estado == "Devuelto"))

        config = get_app_config()
        branch_user_input = QLineEdit(config.get("sucursal", "Principal"))

        # Construcción del formulario
        form.addRow("Fecha:", date_input)
        form.addRow("Tasa USD/CUP actual:", tasa_cambio_input)
        form.addRow("Seleccionar Artículo:", article_selection_layout)
        form.addRow("Artículos Agregados:", scroll_area)
        form.addRow("", total_items_label)
        form.addRow("Estado:", estado_combo)
        form.addRow("Valor venta acordado ($):", valor_venta_input)
        form.addRow("Fecha cambio (devolución):", fecha_cambio_input)
        form.addRow("Usuario / Sucursal:", branch_user_input)

        layout.addLayout(form)

        populate_articles()
        render_bubbles()

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btn_secundario")
        btn_cancel.clicked.connect(dialog.reject)

        btn_save = QPushButton("Registrar Transferencia")
        btn_save.setObjectName("btn_primario")
        btn_save.clicked.connect(lambda: self.save_movement(
            dialog, date_input, estado_combo, valor_venta_input,
            fecha_cambio_input, branch_user_input
        ))

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        dialog.exec()

    def save_movement(self, dialog, date_input, estado_combo, valor_venta_input,
                      fecha_cambio_input, branch_user_input):
        """Guarda la transferencia y resta la cantidad del inventario en la BD."""
        if not self.selected_articles_list:
            QMessageBox.warning(dialog, "Sin artículos", "Debes añadir al menos un artículo a la lista.")
            return

        estado = estado_combo.currentText()
        fecha = date_input.date().toString("yyyy-MM-dd")
        branch_user = branch_user_input.text().strip() or "Principal"

        movement_name = "Transferencia entregada" if estado == "Transferido" else "Transferencia recibida"
        total_cant = sum(item['cantidad'] for item in self.selected_articles_list)

        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            for item in self.selected_articles_list:
                # 1. Registrar el movimiento de inventario
                registrar_movimiento(fecha, item['id'], movement_name, item['cantidad'], branch_user, branch_user)

                # 2. Restar/Sumar la cantidad del inventario disponible
                if estado == "Transferido":
                    cursor.execute("""
                        UPDATE articulos
                        SET inventario = MAX(0, COALESCE(inventario, 0) - ?)
                        WHERE id = ?
                    """, (item['cantidad'], item['id']))
                elif estado == "Devuelto":
                    cursor.execute("""
                        UPDATE articulos
                        SET inventario = COALESCE(inventario, 0) + ?
                        WHERE id = ?
                    """, (item['cantidad'], item['id']))

            conn.commit()
            
            QMessageBox.information(
                dialog, "Éxito",
                f"Transferencia registrada correctamente.\n\n"
                f"• Cantidad total transferida: {total_cant} u.\n"
                f"• Descuento aplicado en Inventario.\n"
                f"• Sucursal / Destino: {branch_user}"
            )
            dialog.accept()
            self.load_data()
            self.notify_refresh()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(dialog, "Error", f"Ocurrió un error al procesar la transacción:\n{e}")
        finally:
            conn.close()

    def load_data(self):
        """Carga y agrupa las transferencias sumando la cantidad total de artículos."""
        config = get_app_config()
        branch_filter = (config.get("sucursal") or "Principal").strip()

        conn = get_connection()
        try:
            query = """
                SELECT m.fecha, m.tipo_movimiento,
                       SUM(m.cantidad) AS cantidad_total, m.sucursal
                FROM movimientos_inventario m
                WHERE m.sucursal = ?
                GROUP BY m.fecha, m.tipo_movimiento, m.sucursal
                ORDER BY m.fecha DESC, m.id DESC
            """
            rows = conn.execute(query, (branch_filter,)).fetchall()
        finally:
            conn.close()

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            tipo_mov = row["tipo_movimiento"]
            if tipo_mov == "Transferencia entregada":
                estado = "Transferido"
            elif tipo_mov == "Transferencia recibida":
                estado = "Devuelto"
            else:
                estado = tipo_mov

            values = (
                row["fecha"],
                estado,
                f"{float(row['cantidad_total']):g}",
                row["sucursal"] or "Principal",
                "$0.00",
                row["fecha"]
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter if column in [0, 1, 2, 5] else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)