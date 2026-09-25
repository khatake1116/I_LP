# ui/views/purchases_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView,
                             QDialog, QFormLayout, QMessageBox, QDoubleSpinBox,
                             QSpinBox, QComboBox, QDateEdit, QMenu, QCompleter,
                             QLineEdit, QTabWidget, QAbstractItemView, QLabel)
from PySide6.QtCore import Qt, QDate, QStringListModel
from datetime import date, datetime, timedelta
from database.connection import get_connection
from core.constants import PurchaseStatus
from core.formatting import format_money, format_money_usd
from database.models import (insert_compra, insert_articulo, get_articulos, update_compra, delete_compra, 
                            get_compra_by_id, get_articulo_by_id, delete_compras_batch, update_compras_estado_batch)
from ui.views.base_view import BaseRefreshView

class CompletePurchaseDialog(QDialog):
    """Diálogo para completar una compra con cantidades recibidas y canceladas."""

    def __init__(self, parent, compra):
        super().__init__(parent)
        self.compra = compra
        self.total = int(compra.get('cantidad', 0))
        self.previous_received = int(compra.get('cantidad_recibida', 0) or 0)

        self.setWindowTitle("Completar compra con cantidades por estado")
        self.setMinimumWidth(420)
        form_layout = QFormLayout(self)

        self.received_spin = QSpinBox(self)
        self.received_spin.setRange(0, self.total)
        self.received_spin.setValue(self.previous_received or (1 if compra.get('recibido') else 0))

        self.cancelled_label = QLabel(self)
        self.cancelled_label.setEnabled(False)
        self.cancelled_label.setObjectName("PurchaseCancelledReadOnly")
        self.cancelled_label.setText(str(max(0, self.total - self.received_spin.value())))

        form_layout.addRow("Cantidad total:", QLabel(str(self.total)))
        form_layout.addRow("Recibidos:", self.received_spin)
        form_layout.addRow("Cancelados/Devueltos:", self.cancelled_label)

        self.received_spin.valueChanged.connect(self._update_cancelled_label)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.setObjectName("btn_guardar")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("btn_cancelar")
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form_layout.addRow(buttons)

        save_btn.clicked.connect(self._guardar)
        cancel_btn.clicked.connect(self.reject)

    def _update_cancelled_label(self):
        cancelados = max(0, self.total - self.received_spin.value())
        self.cancelled_label.setText(str(cancelados))

    def _guardar(self):
        recibidos = self.received_spin.value()
        cancelados = max(0, self.total - recibidos)

        if recibidos == 0 and cancelados == 0:
            QMessageBox.warning(self, "Error", "Debe indicar al menos una cantidad recibida o cancelada.")
            return

        if recibidos > 0:
            estado = PurchaseStatus.COMPLETED.value
        else:
            estado = PurchaseStatus.CANCELLED.value

        fecha_recibido = date.today().isoformat() if recibidos > 0 else None
        if update_compra(
            self.compra['id'],
            self.compra['articulo_id'],
            self.compra['fecha'],
            self.total,
            self.compra['precio_unitario'],
            recibidos > 0,
            fecha_recibido,
            estado,
            recibidos,
            cancelados,
        ):
            QMessageBox.information(self, "Éxito", "La compra fue completada con las cantidades por estado asignadas.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo completar la compra.")


class EditCompletedPurchaseDialog(QDialog):
    """Diálogo para revisar cantidades recibidas y devoluciones post-recepción."""

    def __init__(self, parent, compra):
        super().__init__(parent)
        self.compra = compra
        self.total = int(compra.get('cantidad', 0))
        self.original_received = int(compra.get('cantidad_recibida', 0) or 0)

        self.setWindowTitle("Gestión de defectos y cantidades recibidas")
        self.setMinimumWidth(420)
        form_layout = QFormLayout(self)

        self.received_spin = QSpinBox(self)
        self.received_spin.setRange(0, self.total)
        self.received_spin.setValue(self.original_received)

        self.cancelled_label = QLabel(self)
        self.cancelled_label.setEnabled(False)
        self.cancelled_label.setObjectName("PurchaseCancelledReadOnly")
        self.cancelled_label.setText(str(max(0, self.total - self.received_spin.value())))

        form_layout.addRow("Cantidad Total:", QLabel(str(self.total)))
        form_layout.addRow("Cantidad Recibida:", self.received_spin)
        form_layout.addRow("Cancelados/Devueltos:", self.cancelled_label)

        self.received_spin.valueChanged.connect(self._update_cancelled_label)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.setObjectName("btn_guardar")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("btn_cancelar")
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form_layout.addRow(buttons)

        save_btn.clicked.connect(self._guardar)
        cancel_btn.clicked.connect(self.reject)

    def _update_cancelled_label(self):
        self.cancelled_label.setText(str(max(0, self.total - self.received_spin.value())))

    def _guardar(self):
        nuevo_recibido = self.received_spin.value()
        nuevo_cancelado = max(0, self.total - nuevo_recibido)
        anterior_recibido = self.original_received

        if nuevo_recibido == anterior_recibido:
            QMessageBox.information(self, "Información", "No hubo cambios en la cantidad recibida.")
            return

        if nuevo_recibido > 0:
            estado = PurchaseStatus.COMPLETED.value
        else:
            estado = PurchaseStatus.CANCELLED.value

        fecha_recibido = date.today().isoformat() if nuevo_recibido > 0 else None
        if update_compra(
            self.compra['id'],
            self.compra['articulo_id'],
            self.compra['fecha'],
            self.total,
            self.compra['precio_unitario'],
            nuevo_recibido > 0,
            fecha_recibido,
            estado,
            nuevo_recibido,
            nuevo_cancelado,
        ):
            delta = nuevo_recibido - anterior_recibido
            if delta != 0:
                if delta > 0:
                    detalle = f"Se incorporaron {delta} unidades recibidas al inventario."
                else:
                    detalle = f"Se devolvieron {abs(delta)} unidades al ajuste de compra."
            else:
                detalle = "Se actualizó la revisión del recibo."
            QMessageBox.information(self, "Éxito", detalle)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo actualizar la compra completada.")


class PurchasesView(BaseRefreshView):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Estructura de pestañas
        self.tabs = QTabWidget()
        self.tabs.setObjectName("PurchasesTabs")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Pestaña Compras Pendientes
        self.tab_pendientes = QWidget()
        pendientes_layout = QVBoxLayout(self.tab_pendientes)
        
        # Botones de la pestaña pendientes
        pendientes_btn_layout = QHBoxLayout()
        self.btn_add_pendientes = QPushButton("+ Registrar Compra")
        self.btn_add_pendientes.setObjectName("btn_primario")
        self.btn_add_pendientes.clicked.connect(self.show_add_dialog)
        pendientes_btn_layout.addWidget(self.btn_add_pendientes)
        
        self.btn_edit_pendientes = QPushButton("Editar")
        self.btn_edit_pendientes.setObjectName("btn_primario")
        self.btn_edit_pendientes.setEnabled(False)
        self.btn_edit_pendientes.clicked.connect(self.edit_pendiente)
        pendientes_btn_layout.addWidget(self.btn_edit_pendientes)
        
        self.btn_marcar_completada = QPushButton("Marcar como Completada")
        self.btn_marcar_completada.setObjectName("btn_primario")
        self.btn_marcar_completada.setEnabled(False)
        self.btn_marcar_completada.clicked.connect(self.marcar_como_completada)
        pendientes_btn_layout.addWidget(self.btn_marcar_completada)
        
        self.btn_delete_pendientes = QPushButton("Eliminar")
        self.btn_delete_pendientes.setObjectName("btn_danger")
        self.btn_delete_pendientes.setEnabled(False)
        self.btn_delete_pendientes.clicked.connect(self.delete_selected_pendientes)
        pendientes_btn_layout.addWidget(self.btn_delete_pendientes)
        
        pendientes_btn_layout.addStretch()
        pendientes_layout.addLayout(pendientes_btn_layout)
        
        # Tabla de compras pendientes
        self.table_pendientes = QTableWidget()
        self.table_pendientes.verticalHeader().setVisible(False)
        self.table_pendientes.setColumnCount(7)
        self.table_pendientes.setHorizontalHeaderLabels([
            "Fecha", "Artículo", "Categoría", "Cantidad", "Precio Un.", "Precio Tot.", "Tiempo Transcurrido"
        ])
        self.table_pendientes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.configure_table_sorting(self.table_pendientes)
        self.table_pendientes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_pendientes.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_pendientes.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_pendientes.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_pendientes.customContextMenuRequested.connect(self.show_context_menu_pendientes)
        self.table_pendientes.itemSelectionChanged.connect(self.on_selection_changed_pendientes)
        pendientes_layout.addWidget(self.table_pendientes)
        
        # Pestaña Compras Completadas
        self.tab_completadas = QWidget()
        completadas_layout = QVBoxLayout(self.tab_completadas)
        
        # Botones de la pestaña completadas
        completadas_btn_layout = QHBoxLayout()
        self.btn_edit_completada = QPushButton("Editar (Gestión de Defectos)")
        self.btn_edit_completada.setObjectName("btn_primario")
        self.btn_edit_completada.setEnabled(False)
        self.btn_edit_completada.clicked.connect(self.edit_completada)
        completadas_btn_layout.addWidget(self.btn_edit_completada)
        
        self.btn_delete_completadas = QPushButton("Eliminar")
        self.btn_delete_completadas.setObjectName("btn_danger")
        self.btn_delete_completadas.setEnabled(False)
        self.btn_delete_completadas.clicked.connect(self.delete_selected_completadas)
        completadas_btn_layout.addWidget(self.btn_delete_completadas)
        
        completadas_btn_layout.addStretch()
        completadas_layout.addLayout(completadas_btn_layout)
        
        # Tabla de compras completadas
        self.table_completadas = QTableWidget()
        self.table_completadas.verticalHeader().setVisible(False)
        self.table_completadas.setColumnCount(8)
        self.table_completadas.setHorizontalHeaderLabels([
            "Fecha", "Artículo", "Categoría", "Cantidad Total", "Precio Un.", "Precio Tot.", "Recibidos", "Cancelados/Devueltos"
        ])
        self.table_completadas.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.configure_table_sorting(self.table_completadas)
        self.table_completadas.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_completadas.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_completadas.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_completadas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_completadas.customContextMenuRequested.connect(self.show_context_menu_completadas)
        self.table_completadas.itemSelectionChanged.connect(self.on_selection_changed_completadas)
        completadas_layout.addWidget(self.table_completadas)
        
        # Agregar pestañas
        self.tabs.addTab(self.tab_pendientes, "Compras Pendientes")
        self.tabs.addTab(self.tab_completadas, "Compras Completadas")
        
        layout.addWidget(self.tabs)
        
        self.load_data()

    def on_tab_changed(self, index):
        """Maneja el cambio de pestañas y actualiza los botones."""
        # No se necesita hacer nada especial ya que cada pestaña tiene sus propios botones

    def _table_item(self, text, compra_id):
        item = QTableWidgetItem("" if text is None else str(text))
        item.setData(Qt.UserRole, compra_id)
        return item

    def _compra_ids_from_table(self, table):
        """Obtiene los IDs de compra de las filas seleccionadas, aunque alguna celda esté vacía."""
        compra_ids = []
        selected_rows = set(index.row() for index in table.selectionModel().selectedRows())
        if not selected_rows:
            selected_rows = set(item.row() for item in table.selectedItems())
        for row in selected_rows:
            for col in range(table.columnCount()):
                cell = table.item(row, col)
                if cell is None:
                    continue
                compra_id = cell.data(Qt.UserRole)
                if compra_id:
                    compra_ids.append(compra_id)
                    break
        return compra_ids

    def _refresh_catalog_view(self):
        """Actualiza el catálogo de artículos sin necesidad de reiniciar la app."""
        from ui.views.articles_view import ArticlesView
        window = self.window()
        if window is None:
            return
        for view in window.findChildren(ArticlesView):
            view.load_data()

    def on_selection_changed_pendientes(self):
        """Actualiza el estado de los botones cuando cambia la selección en la tabla de pendientes."""
        has_selection = self.table_pendientes.selectionModel().hasSelection()
        self.btn_edit_pendientes.setEnabled(has_selection)
        self.btn_marcar_completada.setEnabled(has_selection)
        self.btn_delete_pendientes.setEnabled(has_selection)

    def edit_pendiente(self):
        """Edita una compra pendiente para corregir cantidades o precios."""
        compra_ids = self._compra_ids_from_table(self.table_pendientes)
        if len(compra_ids) != 1:
            QMessageBox.information(self, "Editar Compra", "Seleccione exactamente una compra para editar.")
            return
        self.show_edit_dialog_pendiente(compra_ids[0])

    def on_selection_changed_completadas(self):
        """Actualiza el estado de los botones cuando cambia la selección en la tabla de completadas."""
        has_selection = self.table_completadas.selectionModel().hasSelection()
        self.btn_delete_completadas.setEnabled(has_selection)
        self.btn_edit_completada.setEnabled(has_selection)

    def delete_selected_pendientes(self):
        """Elimina las compras seleccionadas de la tabla de pendientes."""
        compra_ids = self._compra_ids_from_table(self.table_pendientes)
        if not compra_ids:
            QMessageBox.warning(self, "Error", "No se pudieron identificar las compras seleccionadas.")
            return
        
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro de eliminar los {len(compra_ids)} elementos seleccionados? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_compras_batch(compra_ids):
                QMessageBox.information(self, "Éxito", f"Se eliminaron {len(compra_ids)} compras correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron eliminar las compras.")

    def delete_selected_completadas(self):
        """Elimina las compras seleccionadas de la tabla de completadas."""
        compra_ids = self._compra_ids_from_table(self.table_completadas)
        if not compra_ids:
            QMessageBox.warning(self, "Error", "No se pudieron identificar las compras seleccionadas.")
            return
        
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro de eliminar los {len(compra_ids)} elementos seleccionados? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_compras_batch(compra_ids):
                QMessageBox.information(self, "Éxito", f"Se eliminaron {len(compra_ids)} compras correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron eliminar las compras.")

    def marcar_como_completada(self):
        """Abre un diálogo para definir la cantidad recibida o cancelada antes de completar la compra."""
        compra_ids = self._compra_ids_from_table(self.table_pendientes)
        if not compra_ids:
            QMessageBox.warning(self, "Error", "No se pudieron identificar las compras seleccionadas.")
            return
        if len(compra_ids) != 1:
            QMessageBox.information(self, "Completar compra", "Seleccione exactamente una compra para completar con cantidades por estado.")
            return

        compra_id = compra_ids[0]
        compra = get_compra_by_id(compra_id)
        if not compra:
            QMessageBox.critical(self, "Error", "No se encontró la compra seleccionada.")
            return

        dialog = CompletePurchaseDialog(self, compra)
        if dialog.exec() == QDialog.Accepted:
            self.load_data()
            self.notify_refresh()

    def edit_completada(self):
        """Edita una compra completada para gestión de defectos y reclamaciones."""
        compra_ids = self._compra_ids_from_table(self.table_completadas)
        if len(compra_ids) != 1:
            QMessageBox.information(self, "Editar Compra", "Seleccione exactamente una compra para editar.")
            return
        self.show_edit_dialog_completada(compra_ids[0])

    def load_data(self):
        """Carga las compras en las pestañas correspondientes según su estado."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Cargar compras pendientes (estados activos/en proceso)
        completed_values = "', '".join(PurchaseStatus.completed_values())
        query_pendientes = f"""
            SELECT 
                c.id,
                c.fecha,
                a.nombre AS articulo,
                a.categoria,
                c.cantidad,
                c.precio_unitario,
                c.recibido,
                c.fecha_recibido,
                c.estado,
                c.cantidad_recibida,
                c.cantidad_cancelada
            FROM compras c
            LEFT JOIN articulos a ON c.articulo_id = a.id
            WHERE c.estado NOT IN ('{completed_values}')
            ORDER BY c.fecha DESC
        """
        cursor.execute(query_pendientes)
        rows_pendientes = cursor.fetchall()
        
        # Cargar compras completadas
        completed_values = "', '".join(PurchaseStatus.completed_values())
        query_completadas = f"""
            SELECT 
                c.id,
                c.fecha,
                a.nombre AS articulo,
                a.categoria,
                c.cantidad,
                c.precio_unitario,
                c.recibido,
                c.fecha_recibido,
                c.estado,
                c.cantidad_recibida,
                c.cantidad_cancelada
            FROM compras c
            LEFT JOIN articulos a ON c.articulo_id = a.id
            WHERE c.estado IN ('{completed_values}')
            ORDER BY c.fecha DESC
        """
        cursor.execute(query_completadas)
        rows_completadas = cursor.fetchall()
        
        conn.close()

        hoy = date.today()
        self.table_pendientes.setSortingEnabled(False)
        self.table_pendientes.setRowCount(len(rows_pendientes))
        
        for row_idx, row in enumerate(rows_pendientes):
            compra_id = row['id']
            cantidad = int(row['cantidad'])
            precio_un = float(row['precio_unitario'])
            precio_tot = cantidad * precio_un
            
            # Calcular tiempo transcurrido
            fecha_compra = datetime.strptime(row['fecha'], '%Y-%m-%d').date()
            dias_transcurridos = (hoy - fecha_compra).days
            
            # Formatear tiempo transcurrido
            if dias_transcurridos == 0:
                tiempo_texto = "Hoy"
            elif dias_transcurridos == 1:
                tiempo_texto = "1 día"
            else:
                tiempo_texto = f"{dias_transcurridos} días"
            
            tiempo_item = self._table_item(tiempo_texto, compra_id)
            if dias_transcurridos > 7:
                tiempo_item.setForeground(Qt.red)
            elif dias_transcurridos > 3:
                tiempo_item.setForeground(Qt.yellow)
            else:
                tiempo_item.setForeground(Qt.green)

            articulo_text = row['articulo'] or "Artículo no encontrado"
            categoria_text = row['categoria'] or "Sin categoría"

            self.table_pendientes.setItem(row_idx, 0, self._table_item(row['fecha'], compra_id))
            self.table_pendientes.setItem(row_idx, 1, self._table_item(articulo_text, compra_id))
            self.table_pendientes.setItem(row_idx, 2, self._table_item(categoria_text, compra_id))
            self.table_pendientes.setItem(row_idx, 3, self._table_item(cantidad, compra_id))
            self.table_pendientes.setItem(row_idx, 4, self._table_item(format_money_usd(precio_un), compra_id))
            self.table_pendientes.setItem(row_idx, 5, self._table_item(format_money_usd(precio_tot), compra_id))
            self.table_pendientes.setItem(row_idx, 6, tiempo_item)

        self.table_pendientes.setSortingEnabled(True)

        self.table_completadas.setSortingEnabled(False)
        self.table_completadas.setRowCount(len(rows_completadas))
        
        for row_idx, row in enumerate(rows_completadas):
            compra_id = row['id']
            cantidad_total = int(row['cantidad'])
            precio_un = float(row['precio_unitario'])
            precio_tot = cantidad_total * precio_un
            recibidos = int(row['cantidad_recibida'] or 0)
            cancelados = int(row['cantidad_cancelada'] or 0)
            articulo_text = row['articulo'] or "Artículo no encontrado"
            categoria_text = row['categoria'] or "Sin categoría"

            self.table_completadas.setItem(row_idx, 0, self._table_item(row['fecha'], compra_id))
            self.table_completadas.setItem(row_idx, 1, self._table_item(articulo_text, compra_id))
            self.table_completadas.setItem(row_idx, 2, self._table_item(categoria_text, compra_id))
            self.table_completadas.setItem(row_idx, 3, self._table_item(cantidad_total, compra_id))
            self.table_completadas.setItem(row_idx, 4, self._table_item(format_money_usd(precio_un), compra_id))
            self.table_completadas.setItem(row_idx, 5, self._table_item(format_money_usd(precio_tot), compra_id))
            self.table_completadas.setItem(row_idx, 6, self._table_item(recibidos, compra_id))
            self.table_completadas.setItem(row_idx, 7, self._table_item(cancelados, compra_id))

        self.table_completadas.setSortingEnabled(True)

    def show_add_dialog(self):
        """Diálogo para registrar una nueva compra con autocompletado y categoría automática."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar Nueva Compra")
        dialog.setMinimumWidth(450)
        
        form_layout = QFormLayout()
        
        articulos = get_articulos()
        articulos_dict = {art['nombre']: art for art in articulos}

        def aplicar_articulo_en_combo(articulo):
            nonlocal articulos_dict
            nombre = articulo['nombre']
            articulos_dict[nombre] = articulo
            if input_articulo.findText(nombre) < 0:
                input_articulo.addItem(nombre)
            input_articulo.setCurrentText(nombre)
            completer.setModel(QStringListModel(list(articulos_dict.keys())))
            actualizar_categoria(nombre)

        input_articulo = QComboBox()
        input_articulo.setEditable(True)
        input_articulo.addItems(list(articulos_dict.keys()))
        input_articulo.setCurrentText("")

        completer = QCompleter(list(articulos_dict.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        input_articulo.setCompleter(completer)
        
        # Etiqueta dinámica para mostrar la categoría de forma automática
        lbl_categoria_val = QPushButton("Seleccione un artículo")
        lbl_categoria_val.setObjectName("PurchaseCategoryStatus")
        lbl_categoria_val.setEnabled(False)
        lbl_categoria_val.setProperty("categoryStatus", "empty")
        
        def actualizar_categoria(text):
            """Actualiza automáticamente la categoría según el artículo seleccionado/escrito."""
            art_info = articulos_dict.get(text)
            if art_info:
                lbl_categoria_val.setText(art_info['categoria'])
                lbl_categoria_val.setProperty("categoryStatus", "valid")
            else:
                lbl_categoria_val.setText("Artículo nuevo / No encontrado en catálogo")
                lbl_categoria_val.setProperty("categoryStatus", "invalid")
            lbl_categoria_val.style().unpolish(lbl_categoria_val)
            lbl_categoria_val.style().polish(lbl_categoria_val)

        input_articulo.currentTextChanged.connect(actualizar_categoria)
        input_articulo.editTextChanged.connect(actualizar_categoria)

        input_fecha = QDateEdit()
        input_fecha.setCalendarPopup(True)
        input_fecha.setDate(QDate.currentDate())
        
        input_cantidad = QSpinBox()
        input_cantidad.setRange(1, 100000)
        input_cantidad.setValue(1)
        
        input_precio = QDoubleSpinBox()
        input_precio.setRange(0, 1000000)
        input_precio.setValue(0.0)
        input_precio.setPrefix("$")
        input_precio.setSuffix(" USD")
        
        form_layout.addRow("Artículo:", input_articulo)
        form_layout.addRow("Categoría (Auto):", lbl_categoria_val)
        form_layout.addRow("Fecha:", input_fecha)
        form_layout.addRow("Cantidad:", input_cantidad)
        form_layout.addRow("Precio Unitario:", input_precio)
        
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def registrar_articulo_faltante(nombre_sugerido=""):
            missing_dialog = QDialog(dialog)
            missing_dialog.setWindowTitle("Registrar artículo faltante")
            missing_dialog.setMinimumWidth(420)
            layout = QFormLayout(missing_dialog)

            nombre_input = QLineEdit(nombre_sugerido)
            categoria_input = QComboBox()
            categoria_input.setEditable(True)
            categoria_input.addItems(sorted({art['categoria'] for art in articulos if art.get('categoria')} | {"General", "Electrónica", "Ropa", "Hogar", "Herramientas", "Calzado"}))
            descripcion_input = QLineEdit()
            descripcion_input.setPlaceholderText("Descripción del artículo")
            peso_input = QDoubleSpinBox()
            peso_input.setRange(0.0, 5000.0)
            peso_input.setValue(0.0)
            peso_input.setDecimals(3)
            peso_input.setSuffix(" lb")

            layout.addRow("Nombre:", nombre_input)
            layout.addRow("Categoría:", categoria_input)
            layout.addRow("Descripción:", descripcion_input)
            layout.addRow("Peso base:", peso_input)

            btn_ok = QPushButton("Guardar artículo")
            btn_ok.setObjectName("btn_guardar")
            btn_cancel = QPushButton("Cancelar")
            btn_cancel.setObjectName("btn_cancelar")

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_row.addWidget(btn_ok)
            btn_row.addWidget(btn_cancel)
            layout.addRow(btn_row)

            created = {"articulo": None}

            def guardar_faltante():
                nombre = nombre_input.text().strip()
                categoria = categoria_input.currentText().strip() or "General"
                descripcion = descripcion_input.text().strip()
                peso = peso_input.value()
                if not nombre:
                    QMessageBox.warning(missing_dialog, "Error", "El nombre del artículo es obligatorio.")
                    return
                articulo_id = insert_articulo(nombre, categoria, peso, descripcion)
                if not articulo_id:
                    QMessageBox.critical(missing_dialog, "Error", "No se pudo registrar el artículo.")
                    return
                articulo_db = get_articulo_by_id(articulo_id) or {
                    "id": articulo_id,
                    "nombre": nombre,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "peso_lb": peso,
                }
                aplicar_articulo_en_combo(articulo_db)
                created["articulo"] = articulo_db
                missing_dialog.accept()

            btn_ok.clicked.connect(guardar_faltante)
            btn_cancel.clicked.connect(missing_dialog.reject)
            if missing_dialog.exec() == QDialog.Accepted:
                return created["articulo"]
            return None

        def guardar():
            nombre_articulo = input_articulo.currentText().strip()
            if not nombre_articulo:
                QMessageBox.warning(dialog, "Error", "Debe indicar un artículo antes de guardar la compra.")
                return

            art_info = articulos_dict.get(nombre_articulo)
            if not art_info:
                art_info = registrar_articulo_faltante(nombre_articulo)
                if not art_info:
                    return

            articulo_id = art_info.get('id')
            fecha = input_fecha.date().toString("yyyy-MM-dd")
            cantidad = input_cantidad.value()
            precio = input_precio.value()
            
            if not articulo_id or articulo_id <= 0:
                QMessageBox.critical(dialog, "Error", "ID de artículo inválido. No se puede registrar la compra.")
                return
            
            if insert_compra(articulo_id, fecha, cantidad, precio, 0, None, PurchaseStatus.DRAFT.value):
                QMessageBox.information(dialog, "Éxito", "Compra registrada correctamente.")
                dialog.accept()
                self.load_data()
                self._refresh_catalog_view()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo registrar la compra en la base de datos.")
        
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dialog.reject)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        
        dialog.exec()

    def show_context_menu_pendientes(self, position):
        """Muestra menú contextual en la tabla de pendientes."""
        item = self.table_pendientes.itemAt(position)
        if not item:
            return

        compra_id = item.data(Qt.UserRole)
        if not compra_id:
            ids = self._compra_ids_from_table(self.table_pendientes)
            compra_id = ids[0] if len(ids) == 1 else None
        if not compra_id:
            QMessageBox.warning(self, "Error", "No se pudo identificar la compra")
            return
        
        menu = QMenu(self)
        action_editar = menu.addAction("Editar")
        action_borrar = menu.addAction("Borrar")
        
        action = menu.exec(self.table_pendientes.mapToGlobal(position))
        
        if action == action_editar:
            self.show_edit_dialog(compra_id)
        elif action == action_borrar:
            self.delete_compra_row(compra_id)

    def show_context_menu_completadas(self, position):
        """Muestra menú contextual en la tabla de completadas."""
        item = self.table_completadas.itemAt(position)
        if not item:
            return

        compra_id = item.data(Qt.UserRole)
        if not compra_id:
            ids = self._compra_ids_from_table(self.table_completadas)
            compra_id = ids[0] if len(ids) == 1 else None
        if not compra_id:
            QMessageBox.warning(self, "Error", "No se pudo identificar la compra")
            return
        
        menu = QMenu(self)
        action_editar = menu.addAction("Editar (Gestión de Defectos)")
        action_borrar = menu.addAction("Borrar")
        
        action = menu.exec(self.table_completadas.mapToGlobal(position))
        
        if action == action_editar:
            self.show_edit_dialog_completada(compra_id)
        elif action == action_borrar:
            self.delete_compra_row(compra_id)

    def show_edit_dialog_pendiente(self, compra_id):
        """Diálogo simplificado para editar una compra pendiente (cantidad y precio)."""
        compra = get_compra_by_id(compra_id)
        if not compra:
            QMessageBox.critical(self, "Error", "No se encontró la compra.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Compra Pendiente")
        dialog.setMinimumWidth(400)
        
        form_layout = QFormLayout()
        
        articulos = get_articulos()
        articulos_dict = {art['nombre']: art for art in articulos}
        
        # Buscar el nombre del artículo actual
        nombre_actual = ""
        for art in articulos:
            if art['id'] == compra['articulo_id']:
                nombre_actual = art['nombre']
                break
        
        form_layout.addRow("Artículo:", QLabel(nombre_actual))
        form_layout.addRow("Fecha:", QLabel(str(compra['fecha'])))
        
        input_cantidad = QSpinBox()
        input_cantidad.setRange(1, 100000)
        input_cantidad.setValue(compra['cantidad'])
        form_layout.addRow("Cantidad:", input_cantidad)
        
        input_precio = QDoubleSpinBox()
        input_precio.setRange(0, 1000000)
        input_precio.setValue(compra['precio_unitario'])
        input_precio.setPrefix("$")
        input_precio.setSuffix(" USD")
        form_layout.addRow("Precio Unitario:", input_precio)
        
        combo_estado = QComboBox()
        combo_estado.addItems([
            PurchaseStatus.DRAFT.value,
            PurchaseStatus.SENT.value,
            PurchaseStatus.PARTIAL.value,
        ])
        combo_estado.setCurrentText(compra.get('estado', PurchaseStatus.DRAFT.value))
        form_layout.addRow("Estado:", combo_estado)
        
        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            cantidad = input_cantidad.value()
            precio = input_precio.value()
            estado = combo_estado.currentText()
            
            # En compras pendientes, mantenemos recibido=0
            if update_compra(compra_id, compra['articulo_id'], compra['fecha'], cantidad, precio, 0, None, estado):
                QMessageBox.information(dialog, "Éxito", "Compra actualizada correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo actualizar la compra.")
        
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dialog.reject)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        
        dialog.exec()

    def show_edit_dialog(self, compra_id):
        """Diálogo para editar una compra existente con la misma lógica de autocompletado."""
        compra = get_compra_by_id(compra_id)
        if not compra:
            QMessageBox.critical(self, "Error", "No se encontró la compra.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Compra")
        dialog.setMinimumWidth(450)
        
        form_layout = QFormLayout()
        
        articulos = get_articulos()
        articulos_dict = {art['nombre']: art for art in articulos}
        
        input_articulo = QComboBox()
        input_articulo.setEditable(True)
        input_articulo.addItems(list(articulos_dict.keys()))
        
        # Buscar el nombre del artículo actual mediante su ID para seleccionarlo por defecto
        nombre_actual = ""
        for art in articulos:
            if art['id'] == compra['articulo_id']:
                nombre_actual = art['nombre']
                break
                
        input_articulo.setCurrentText(nombre_actual)
        
        completer = QCompleter(list(articulos_dict.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        input_articulo.setCompleter(completer)
        
        lbl_categoria_val = QPushButton()
        lbl_categoria_val.setObjectName("PurchaseCategoryStatus")
        lbl_categoria_val.setEnabled(False)
        lbl_categoria_val.setProperty("categoryStatus", "valid")
        
        def actualizar_categoria(text):
            art_info = articulos_dict.get(text)
            if art_info:
                lbl_categoria_val.setText(art_info['categoria'])
                lbl_categoria_val.setProperty("categoryStatus", "valid")
            else:
                lbl_categoria_val.setText("Artículo no encontrado")
                lbl_categoria_val.setProperty("categoryStatus", "invalid")
            lbl_categoria_val.style().unpolish(lbl_categoria_val)
            lbl_categoria_val.style().polish(lbl_categoria_val)

        actualizar_categoria(nombre_actual)
        input_articulo.currentTextChanged.connect(actualizar_categoria)
        input_articulo.editTextChanged.connect(actualizar_categoria)
        
        input_fecha = QDateEdit()
        input_fecha.setCalendarPopup(True)
        input_fecha.setDate(QDate.fromString(compra['fecha'], "yyyy-MM-dd"))
        
        input_cantidad = QSpinBox()
        input_cantidad.setRange(1, 100000)
        input_cantidad.setValue(compra['cantidad'])
        
        input_precio = QDoubleSpinBox()
        input_precio.setRange(0, 1000000)
        input_precio.setValue(compra['precio_unitario'])
        input_precio.setPrefix("$")
        input_precio.setSuffix(" USD")
        
        combo_estado = QComboBox()
        combo_estado.addItems([
            PurchaseStatus.DRAFT.value,
            PurchaseStatus.SENT.value,
            PurchaseStatus.PARTIAL.value,
        ])
        combo_estado.setCurrentText(compra.get('estado', PurchaseStatus.DRAFT.value))
        
        combo_recibido = QComboBox()
        combo_recibido.addItem("NO (En Tránsito)", 0)
        combo_recibido.addItem("SÍ (Recibido)", 1)
        combo_recibido.setCurrentIndex(1 if compra['recibido'] else 0)
        
        # Campo de fecha de recepción
        input_fecha_recibido = QDateEdit()
        input_fecha_recibido.setCalendarPopup(True)
        if compra['fecha_recibido']:
            input_fecha_recibido.setDate(QDate.fromString(compra['fecha_recibido'], "yyyy-MM-dd"))
        else:
            input_fecha_recibido.setDate(QDate.currentDate())
        input_fecha_recibido.setVisible(compra['recibido'])
        
        # Mostrar fecha de recepción cuando se selecciona "Recibido"
        def on_recibido_changed_edit(index):
            recibido = combo_recibido.currentData()
            input_fecha_recibido.setVisible(recibido == 1)
            if recibido == 1 and not compra['fecha_recibido']:
                input_fecha_recibido.setDate(QDate.currentDate())
        
        combo_recibido.currentIndexChanged.connect(on_recibido_changed_edit)
        
        form_layout.addRow("Artículo:", input_articulo)
        form_layout.addRow("Categoría (Auto):", lbl_categoria_val)
        form_layout.addRow("Fecha:", input_fecha)
        form_layout.addRow("Cantidad:", input_cantidad)
        form_layout.addRow("Precio Unitario:", input_precio)
        form_layout.addRow("Estado:", combo_estado)
        form_layout.addRow("Estado Recepción:", combo_recibido)
        form_layout.addRow("Fecha Recepción:", input_fecha_recibido)
        
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            nombre_articulo = input_articulo.currentText().strip()
            art_info = articulos_dict.get(nombre_articulo)
            
            if not art_info:
                QMessageBox.warning(dialog, "Error", "El artículo especificado no existe en el catálogo.")
                return
            
            articulo_id = art_info['id']
            fecha = input_fecha.date().toString("yyyy-MM-dd")
            cantidad = input_cantidad.value()
            precio = input_precio.value()
            estado = combo_estado.currentText()
            recibido = combo_recibido.currentData()
            
            # Lógica de fecha de recepción
            fecha_recibido = None
            if recibido == 1:
                # Usar fecha actual automáticamente si no tenía fecha
                if not compra['fecha_recibido']:
                    fecha_recibido = date.today().isoformat()
                else:
                    fecha_recibido = input_fecha_recibido.date().toString("yyyy-MM-dd")
            
            if update_compra(compra_id, articulo_id, fecha, cantidad, precio, recibido, fecha_recibido, estado):
                QMessageBox.information(dialog, "Éxito", "Compra actualizada correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo actualizar la compra.")

    def show_edit_dialog_completada(self, compra_id):
        """Diálogo para editar una compra completada revisando cantidades recibidas y devoluciones."""
        compra = get_compra_by_id(compra_id)
        if not compra:
            QMessageBox.critical(self, "Error", "No se encontró la compra.")
            return

        dialog = EditCompletedPurchaseDialog(self, compra)
        if dialog.exec() == QDialog.Accepted:
            self.load_data()
            self.notify_refresh()

    def delete_compra_row(self, compra_id):
        """Elimina una compra después de confirmación."""
        reply = QMessageBox.question(
            self, "Confirmar Borrado",
            "¿Está seguro de que desea eliminar esta compra?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_compra(compra_id):
                QMessageBox.information(self, "Éxito", "Compra eliminada correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar la compra.")