# ui/views/shipments_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView,
                               QDialog, QLineEdit, QFormLayout, QMessageBox, QDoubleSpinBox,
                               QSpinBox, QComboBox, QDateEdit, QMenu, QLabel, QCompleter,
                               QTabWidget, QAbstractItemView, QScrollArea)
from PySide6.QtCore import Qt, QDate
from datetime import datetime, date
from database.connection import get_connection
from core.constants import ShipmentStatus
from core.formatting import format_money, format_money_usd, format_custom_number
from database.models import (insert_envio, insert_envios_batch, get_articulos, update_envio, delete_envio, 
                            get_envio_by_id, get_articulos_disponibles, get_destinatarios,
                            get_destinatario_by_nombre, insert_destinatario,
                            get_stock_disponible, delete_envios_batch, update_envios_estado_batch)
from ui.views.base_view import BaseRefreshView

class ShipmentsView(BaseRefreshView):
    def __init__(self, filter_type="all"):
        """
        filter_type: 'all' (todos), 'pending' (pendientes), 'completed' (completados)
        """
        self.filter_type = filter_type
        self.tarifa_view_mode = "total"  # 'total' para Costo Total, 'unit' para Tarifa por unidad
        super().__init__()
        layout = QVBoxLayout(self)

        # Controles superiores
        btn_layout = QHBoxLayout()
        
        # Solo mostrar botón de registrar envío en la vista de pendientes
        if self.filter_type == "pending":
            self.btn_add = QPushButton("+ Registrar Envío")
            self.btn_add.setObjectName("LogisticsPrimaryButton")
            self.btn_add.clicked.connect(self.show_add_dialog)
            btn_layout.addWidget(self.btn_add)
            
            self.btn_marcar_completado = QPushButton("Marcar como Completado")
            self.btn_marcar_completado.setObjectName("btn_primario")
            self.btn_marcar_completado.setEnabled(False)
            self.btn_marcar_completado.clicked.connect(self.marcar_como_completado)
            btn_layout.addWidget(self.btn_marcar_completado)
        elif self.filter_type == "completed":
            # En la vista de completados, mostrar botón de editar
            self.btn_edit = QPushButton("Editar Envío")
            self.btn_edit.setObjectName("btn_primario")
            self.btn_edit.setEnabled(False)
            self.btn_edit.clicked.connect(self.edit_selected)
            btn_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Tabla de envíos (resumida por orden, no por artículo)
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(7)
        if self.filter_type == "pending":
            headers = [
                "Fecha", "Destinatario", "Método", "Cobro",
                "Peso / Dimensiones (lb)", "Tarifa", "Tiempo Transcurrido"
            ]
        else:
            headers = [
                "Fecha", "Destinatario", "Método", "Cobro",
                "Peso / Dimensiones (lb)", "Tarifa", "Estado"
            ]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellClicked.connect(self.on_tarifa_cell_clicked)
        # Permitir clic en el encabezado de la columna Tarifa para alternar vista
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        layout.addWidget(self.table)

        self.load_data()

    def _shipment_time_ago(self, fecha_str):
        """Calcula el tiempo transcurrido desde la creación del envío."""
        if not fecha_str:
            return "Sin fecha"
        try:
            fecha_creacion = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                fecha_creacion = datetime.fromisoformat(fecha_str).date()
            except ValueError:
                return "Sin fecha"

        diff = date.today() - fecha_creacion
        total_days = diff.days
        if total_days <= 0:
            return "Hoy"
        if total_days == 1:
            return "Hace 1 día"
        if total_days < 30:
            return f"Hace {total_days} días"
        months = total_days // 30
        if months == 1:
            return "Hace 1 mes"
        return f"Hace {months} meses"

    def _build_tooltip_html(self, grouped_items):
        """Genera el tooltip HTML con el contenido consolidado del envío."""
        lines = ["<b>📦 Contenido del Envío</b><br>"]
        for item in grouped_items:
            article_name = str(item["nombre"]).strip() or "Artículo sin nombre"
            qty = int(item["cantidad"] or 0)
            peso_unitario = float(item["peso_unitario"] or 0.0)
            subtotal = qty * peso_unitario
            lines.append(f"• {qty} {article_name} ({format_custom_number(peso_unitario)} lb c/u) = {format_custom_number(subtotal)} lb<br>")

        total_weight = sum(float(item["cantidad"] or 0) * float(item["peso_unitario"] or 0.0) for item in grouped_items)
        lines.append(f"<b>Total Peso:</b> {format_custom_number(total_weight)} lb")
        return "".join(lines)

    def on_selection_changed(self):
        """Actualiza el estado de los botones cuando cambia la selección."""
        has_selection = self.table.selectionModel().hasSelection()
        self.btn_delete.setEnabled(has_selection)

    def on_tarifa_cell_clicked(self, row, column):
        """Maneja el clic en celdas para alternar la vista de la columna Tarifa."""
        # Columna Tarifa es índice 5 (Fecha=0, Destinatario=1, Método=2, Cobro=3, Peso=4, Tarifa=5)
        if column == 5:
            self.toggle_tarifa_view()

    def on_header_clicked(self, logical_index):
        """Maneja el clic en el encabezado para alternar la vista de la columna Tarifa."""
        # Columna Tarifa es índice 5
        if logical_index == 5:
            self.toggle_tarifa_view()

    def toggle_tarifa_view(self):
        """Alterna entre mostrar Costo Total y Tarifa por unidad en la columna Tarifa."""
        self.tarifa_view_mode = "unit" if self.tarifa_view_mode == "total" else "total"
        self.load_data()  # Recargar datos con la nueva vista

    def _selected_envio_ids(self):
        """Recupera todos los IDs de envíos asociados a filas seleccionadas."""
        envio_ids = []
        selected_rows = set(item.row() for item in self.table.selectedItems())
        for row in selected_rows:
            item = self.table.item(row, 0)
            if not item:
                continue
            ids = item.data(Qt.UserRole) or []
            if isinstance(ids, list):
                envio_ids.extend(ids)
            elif ids:
                envio_ids.append(ids)
        return list(dict.fromkeys(envio_ids))

    def edit_selected(self):
        """Edita el envío seleccionado."""
        selected_rows = self.table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            QMessageBox.information(self, "Editar Envío", "Seleccione exactamente un envío para editar.")
            return
        
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if item:
            ids = item.data(Qt.UserRole) or []
            if isinstance(ids, list) and ids:
                self.show_edit_dialog(ids[0])

    def delete_selected(self):
        """Elimina los envíos seleccionados."""
        envio_ids = self._selected_envio_ids()
        if not envio_ids:
            QMessageBox.information(self, "Eliminar", "No hay filas seleccionadas.")
            return
        
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro de eliminar los {len(envio_ids)} elementos seleccionados? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_envios_batch(envio_ids):
                QMessageBox.information(self, "Éxito", f"Se eliminaron {len(envio_ids)} envíos correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron eliminar los envíos.")

    def marcar_como_completado(self):
        """Marca los envíos seleccionados como completados."""
        envio_ids = self._selected_envio_ids()
        if not envio_ids:
            QMessageBox.information(self, "Marcar como Completado", "No hay filas seleccionadas.")
            return
        
        reply = QMessageBox.question(
            self, 
            "Confirmar Completado",
            f"¿Está seguro de marcar {len(envio_ids)} envíos como completados (Entregados)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if update_envios_estado_batch(envio_ids, ShipmentStatus.DELIVERED.value):
                QMessageBox.information(self, "Éxito", f"Se completaron {len(envio_ids)} envíos correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron completar los envíos.")

    def load_data(self):
        """Carga los envíos según el filtro especificado."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Construir consulta según el tipo de filtro
        if self.filter_type == "pending":
            pending_values = "', '".join(ShipmentStatus.pending_values())
            where_clause = f"WHERE e.estado_envio IN ('{pending_values}')"
        elif self.filter_type == "completed":
            completed_values = "', '".join(ShipmentStatus.completed_values())
            where_clause = f"WHERE e.estado_envio IN ('{completed_values}')"
        else:
            where_clause = ""
        
        query = f"""
            SELECT 
                e.id,
                e.fecha,
                a.nombre AS articulo,
                a.peso_lb,
                e.destinatario,
                e.cantidad,
                e.metodo_envio,
                e.costo_lb,
                e.modalidad_cobro,
                e.peso_cobrado,
                e.largo_cm,
                e.ancho_cm,
                e.alto_cm,
                e.costo_calculado,
                e.estado_envio,
                e.recibido,
                e.fecha_recibido
            FROM envios e
            LEFT JOIN articulos a ON e.articulo_id = a.id
            {where_clause}
            ORDER BY e.fecha DESC, e.id DESC
        """
        cursor.execute(query)
        raw_rows = cursor.fetchall()
        conn.close()

        grouped = {}
        for row in raw_rows:
            destinatario = str(row['destinatario']) if row['destinatario'] else "Sin destinatario"
            metodo = str(row['metodo_envio']) if row['metodo_envio'] else "No especificado"
            estado = row['estado_envio'] or ShipmentStatus.IN_TRANSIT.value
            key = (
                row['fecha'] or '',
                destinatario,
                metodo,
                row['modalidad_cobro'] or 'Peso',
                estado,
            )
            if key not in grouped:
                grouped[key] = {
                    'fecha': row['fecha'] or '',
                    'destinatario': destinatario,
                    'metodo': metodo,
                    'modalidad': row['modalidad_cobro'] or 'Peso',
                    'estado': estado,
                    'costo_lb': float(row['costo_lb'] or 0.0),
                    'ids': [],
                    'items': [],
                    'costo_total': 0.0,
                }
            grouped[key]['ids'].append(int(row['id']))
            peso_unitario = float(row['peso_lb'] or 0.0)
            qty = int(row['cantidad'] or 0)
            item_total = float(row['costo_calculado'] or 0.0)
            grouped[key]['costo_total'] += item_total
            grouped[key]['items'].append({
                'nombre': str(row['articulo']) if row['articulo'] else 'Artículo no encontrado',
                'cantidad': qty,
                'peso_unitario': peso_unitario,
            })

        visible_rows = list(grouped.values())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible_rows))

        for row_idx, row in enumerate(visible_rows):
            fecha = row['fecha'] or ''
            destinatario = row['destinatario']
            metodo = row['metodo']
            modalidad = row['modalidad']
            estado = row['estado']
            ids = row['ids']
            items = row['items']
            total_weight = sum(float(item['cantidad'] or 0) * float(item['peso_unitario'] or 0.0) for item in items)
            costo_total = float(row['costo_total'] or 0.0)
            costo_lb = float(row['costo_lb'] or 0.0)

            fecha_item = QTableWidgetItem(fecha)
            fecha_item.setData(Qt.UserRole, ids)
            fecha_item.setToolTip(self._build_tooltip_html(items))
            self.table.setItem(row_idx, 0, fecha_item)

            destinatario_item = QTableWidgetItem(destinatario)
            destinatario_item.setData(Qt.UserRole, ids)
            destinatario_item.setToolTip(self._build_tooltip_html(items))
            self.table.setItem(row_idx, 1, destinatario_item)

            metodo_item = QTableWidgetItem(metodo)
            metodo_item.setData(Qt.UserRole, ids)
            metodo_item.setToolTip(self._build_tooltip_html(items))
            self.table.setItem(row_idx, 2, metodo_item)

            # Normalizar modalidad de cobro para mostrar texto claro
            if modalidad == "Peso":
                modalidad_texto = "Pesaje"
            elif modalidad == "Contenedor":
                modalidad_texto = "Contenedor"
            else:
                modalidad_texto = modalidad
            
            cobro_item = QTableWidgetItem(modalidad_texto)
            cobro_item.setData(Qt.UserRole, ids)
            cobro_item.setToolTip(self._build_tooltip_html(items))
            self.table.setItem(row_idx, 3, cobro_item)

            weight_value = format_custom_number(total_weight)
            weight_item = QTableWidgetItem(weight_value)
            weight_item.setData(Qt.UserRole, ids)
            weight_item.setToolTip(self._build_tooltip_html(items))
            self.table.setItem(row_idx, 4, weight_item)

            # Columna Tarifa unificada: muestra Costo Total o Tarifa por unidad según modo
            if self.tarifa_view_mode == "total":
                tarifa_valor = format_money_usd(costo_total)
                tarifa_tooltip = f"Costo Total: {format_money_usd(costo_total)} USD (clic para ver tarifa/unidad)"
            else:
                tarifa_valor = format_money_usd(costo_lb)
                tarifa_tooltip = f"Tarifa por lb: {format_money_usd(costo_lb)} USD/lb (clic para ver costo total)"
            
            tarifa_item = QTableWidgetItem(tarifa_valor)
            tarifa_item.setData(Qt.UserRole, ids)
            tarifa_item.setToolTip(tarifa_tooltip)
            self.table.setItem(row_idx, 5, tarifa_item)

            if self.filter_type == "pending":
                time_label = self._shipment_time_ago(fecha)
                time_item = QTableWidgetItem(time_label)
                time_item.setData(Qt.UserRole, ids)
                time_item.setToolTip(self._build_tooltip_html(items))
                self.table.setItem(row_idx, 6, time_item)
            else:
                estado_item = QTableWidgetItem(estado)
                estado_item.setData(Qt.UserRole, ids)
                estado_item.setToolTip(self._build_tooltip_html(items))
                if estado == ShipmentStatus.DELIVERED.value:
                    estado_item.setForeground(Qt.green)
                elif estado in ShipmentStatus.completed_values():
                    estado_item.setForeground(Qt.red)
                else:
                    estado_item.setForeground(Qt.yellow)
                self.table.setItem(row_idx, 6, estado_item)

        self.table.setSortingEnabled(True)
        self.configure_table_sorting(self.table)

    def show_add_dialog(self):
        """Muestra el diálogo para registrar un nuevo envío con múltiples artículos."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar Nuevo Envío")
        dialog.setMinimumWidth(550)
        dialog.setMinimumHeight(600)
        
        # Crear scroll area para el contenido
        scroll_area = QScrollArea()
        scroll_area.setObjectName("ShipmentDialogScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Widget contenedor para el contenido
        content_widget = QWidget()
        content_widget.setObjectName("ShipmentDialogContent")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Sección de datos comunes del envío
        common_group = QLabel("Datos Comunes del Envío")
        common_group.setObjectName("ShipmentDialogSection")
        main_layout.addWidget(common_group)
        
        common_layout = QFormLayout()
        
        input_fecha = QDateEdit()
        input_fecha.setCalendarPopup(True)
        input_fecha.setDate(QDate.currentDate())
        
        input_destinatario = QLineEdit()
        
        # Configurar autocompletado de destinatarios
        destinatarios = get_destinatarios()
        destinatario_names = [d['nombre'] for d in destinatarios]
        completer = QCompleter(destinatario_names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        input_destinatario.setCompleter(completer)
        
        input_metodo = QComboBox()
        input_metodo.addItems(["Aéreo", "Marítimo", "Terrestre", "Courier"])

        # Selector de modalidad de cobro
        combo_modalidad = QComboBox()
        combo_modalidad.addItems(["Pesaje", "Contenedor / Dimensiones"])
        combo_modalidad.setCurrentText("Pesaje")

        input_costo = QDoubleSpinBox()
        input_costo.setRange(0, 1000000)
        input_costo.setValue(0)
        input_costo.setPrefix("$")
        input_costo.setSuffix(" USD")

        # Campos de dimensiones para contenedor (deshabilitados por defecto)
        input_largo = QDoubleSpinBox()
        input_largo.setRange(0, 5000)
        input_largo.setValue(0)
        input_largo.setSuffix(" cm")
        input_largo.setEnabled(False)

        input_ancho = QDoubleSpinBox()
        input_ancho.setRange(0, 5000)
        input_ancho.setValue(0)
        input_ancho.setSuffix(" cm")
        input_ancho.setEnabled(False)

        input_alto = QDoubleSpinBox()
        input_alto.setRange(0, 5000)
        input_alto.setValue(0)
        input_alto.setSuffix(" cm")
        input_alto.setEnabled(False)

        combo_estado = QComboBox()
        combo_estado.addItems([
            ShipmentStatus.IN_TRANSIT.value,
            ShipmentStatus.DELIVERED.value,
            ShipmentStatus.RETURNED.value,
            ShipmentStatus.CANCELLED.value,
        ])
        combo_estado.setCurrentText(ShipmentStatus.IN_TRANSIT.value)

        # Contenedor para campos de dimensiones (oculto por defecto en modo Pesaje)
        dimensiones_container = QWidget()
        dimensiones_layout = QFormLayout(dimensiones_container)
        dimensiones_layout.addRow("Largo:", input_largo)
        dimensiones_layout.addRow("Ancho:", input_ancho)
        dimensiones_layout.addRow("Alto:", input_alto)
        dimensiones_container.setVisible(False)  # Oculto por defecto
        
        # Función para manejar cambio de modalidad
        def on_modalidad_changed():
            modalidad = combo_modalidad.currentText()
            if modalidad == "Pesaje":
                input_costo.setEnabled(True)
                input_costo.setPrefix("$")
                input_costo.setSuffix(" USD")
                dimensiones_container.setVisible(False)  # Ocultar dimensiones
            else:  # Contenedor / Dimensiones
                input_costo.setEnabled(True)
                input_costo.setPrefix("$")
                input_costo.setSuffix(" USD (Tarifa Plana)")
                dimensiones_container.setVisible(True)  # Mostrar dimensiones

        combo_modalidad.currentTextChanged.connect(on_modalidad_changed)

        common_layout.addRow("Fecha:", input_fecha)
        common_layout.addRow("Destinatario:", input_destinatario)
        common_layout.addRow("Método de Envío:", input_metodo)
        common_layout.addRow("Modalidad de Cobro:", combo_modalidad)
        common_layout.addRow("Tarifa:", input_costo)
        common_layout.addRow(dimensiones_container)  # Contenedor de dimensiones
        common_layout.addRow("Estado:", combo_estado)

        main_layout.addLayout(common_layout)
        
        # Separador
        separator = QLabel("─" * 50)
        separator.setObjectName("ShipmentSeparator")
        separator.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(separator)
        
        # Sección de artículos
        articles_group = QLabel("Artículos a Enviar (Múltiples)")
        articles_group.setObjectName("ShipmentDialogSection")
        main_layout.addWidget(articles_group)
        
        # Lista de artículos agregados
        self.shipment_items = []  # Lista de diccionarios: {articulo_id, nombre, cantidad}
        
        # Tabla temporal para mostrar artículos agregados
        items_table = QTableWidget()
        items_table.setObjectName("ShipmentItemsTable")
        items_table.setColumnCount(3)
        items_table.setHorizontalHeaderLabels(["Artículo", "Cantidad", "Acción"])
        items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Artículo se estira
        items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Cantidad se ajusta
        items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Acción se ajusta
        items_table.verticalHeader().setVisible(False)
        items_table.setMaximumHeight(150)
        items_table.setMinimumHeight(100)
        main_layout.addWidget(items_table)
        
        # Controles para agregar artículo
        add_layout = QHBoxLayout()
        
        articulos = get_articulos_disponibles()
        combo_articulo = QComboBox()

        if not articulos:
            combo_articulo.addItem("No hay artículos disponibles en Stock A1")
            combo_articulo.setEnabled(False)
        else:
            for art in articulos:
                stock_actual = int(art.get('stock_disponible', 0) or 0)
                combo_articulo.addItem(f"{art['nombre']} ({art['categoria']}) - stock A1: {stock_actual}", art['id'])

        input_cantidad = QSpinBox()
        input_cantidad.setRange(1, 100000)
        input_cantidad.setValue(1)
        input_cantidad.setPrefix("x ")

        if articulos:
            articulo_actual = combo_articulo.currentData()
            stock_actual = next((int(item.get('stock_disponible', 0) or 0) for item in articulos if item.get('id') == articulo_actual), 0)
            input_cantidad.setMaximum(stock_actual)
            input_cantidad.setValue(min(1, stock_actual))

        def actualizar_cantidad_maxima():
            if not articulos:
                input_cantidad.setEnabled(False)
                return
            articulo_id = combo_articulo.currentData()
            stock_actual = next((int(item.get('stock_disponible', 0) or 0) for item in articulos if item.get('id') == articulo_id), 0)
            input_cantidad.setRange(1, stock_actual if stock_actual > 0 else 1)
            if stock_actual <= 0:
                QMessageBox.warning(dialog, "Sin stock", "No hay existencias disponibles en Stock A1 para despachar este artículo.")
                input_cantidad.setValue(1)
                input_cantidad.setEnabled(False)
                return
            if input_cantidad.value() > stock_actual:
                input_cantidad.setValue(stock_actual)
            input_cantidad.setEnabled(True)

        combo_articulo.currentIndexChanged.connect(actualizar_cantidad_maxima)
        actualizar_cantidad_maxima()
        
        btn_add_item = QPushButton("+ Agregar Artículo")
        btn_add_item.setObjectName("btn_guardar")
        
        add_layout.addWidget(QLabel("Artículo:"))
        add_layout.addWidget(combo_articulo)
        add_layout.addWidget(input_cantidad)
        add_layout.addWidget(btn_add_item)
        main_layout.addLayout(add_layout)
        
        # Función para actualizar la tabla de artículos
        def update_items_table():
            items_table.setRowCount(len(self.shipment_items))
            for row_idx, item in enumerate(self.shipment_items):
                # Solo mostrar el nombre del artículo, sin ID
                items_table.setItem(row_idx, 0, QTableWidgetItem(item['nombre']))
                items_table.setItem(row_idx, 1, QTableWidgetItem(str(item['cantidad'])))
                
                btn_remove = QPushButton("✕")
                btn_remove.setObjectName("ShipmentRemoveButton")
                btn_remove.setFixedWidth(30)
                btn_remove.clicked.connect(lambda checked=False, idx=row_idx: remove_item(idx))
                items_table.setCellWidget(row_idx, 2, btn_remove)
        
        def remove_item(index):
            """Elimina un artículo de la lista."""
            if 0 <= index < len(self.shipment_items):
                self.shipment_items.pop(index)
                update_items_table()
        
        def add_item():
            """Agrega un artículo a la lista."""
            articulo_id = combo_articulo.currentData()
            cantidad = input_cantidad.value()

            if not articulo_id or not articulos:
                QMessageBox.warning(dialog, "Error", "Debe seleccionar un artículo con stock disponible.")
                return

            stock_actual = next((int(item.get('stock_disponible', 0) or 0) for item in articulos if item.get('id') == articulo_id), 0)
            if stock_actual <= 0:
                QMessageBox.warning(dialog, "Stock insuficiente", "No hay existencias disponibles en Stock A1 para despachar este artículo.")
                return
            if cantidad > stock_actual:
                QMessageBox.warning(dialog, "Stock insuficiente", f"La cantidad máxima disponible para este artículo es {stock_actual}.")
                input_cantidad.setValue(stock_actual)
                return

            nombre = combo_articulo.currentText().split(" (")[0]

            for item in self.shipment_items:
                if item['articulo_id'] == articulo_id:
                    nuevo_total = item['cantidad'] + cantidad
                    if nuevo_total > stock_actual:
                        QMessageBox.warning(dialog, "Stock insuficiente", f"Solo hay {stock_actual} unidades disponibles de este artículo.")
                        return
                    item['cantidad'] = nuevo_total
                    update_items_table()
                    return

            self.shipment_items.append({
                'articulo_id': articulo_id,
                'nombre': nombre,
                'cantidad': cantidad
            })
            update_items_table()
        
        btn_add_item.clicked.connect(add_item)
        
        # Botones de guardar/cancelar
        btn_layout = QHBoxLayout()
        btn_guardar = QPushButton("Guardar Envío")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")

        def guardar():
            fecha = input_fecha.date().toString("yyyy-MM-dd")
            destinatario = input_destinatario.text().strip()
            metodo = input_metodo.currentText()
            modalidad = combo_modalidad.currentText()
            costo = input_costo.value()
            largo = input_largo.value()
            ancho = input_ancho.value()
            alto = input_alto.value()
            estado = combo_estado.currentText()
            recibido = 1 if estado == ShipmentStatus.DELIVERED.value else 0
            
            if not destinatario:
                QMessageBox.warning(dialog, "Error", "El destinatario es obligatorio.")
                return
            
            if not self.shipment_items:
                QMessageBox.warning(dialog, "Error", "Debe agregar al menos un artículo al envío.")
                return

            for item in self.shipment_items:
                stock_disponible = get_stock_disponible(item['articulo_id'])
                if item['cantidad'] > stock_disponible:
                    QMessageBox.warning(
                        dialog,
                        "Stock insuficiente",
                        f"No hay stock suficiente para '{item['nombre']}'. "
                        f"Disponible: {stock_disponible}; solicitado: {item['cantidad']}."
                    )
                    return

            # Cálculo diferenciado según modalidad de cobro
            costo_calculado = 0.0
            modalidad_db = "Peso"  # Valor por defecto para base de datos
            
            if modalidad == "Pesaje":
                # Cálculo por peso: Costo Total = Peso Total (lb) × Tarifa por Libra (USD)
                modalidad_db = "Peso"
                for item in self.shipment_items:
                    costo_calculado += item['cantidad'] * costo
            else:
                # Contenedor / Dimensiones: Tarifa plana negociada
                modalidad_db = "Contenedor"
                costo_calculado = costo  # Tarifa plana del contenedor
            
            destinatario_existente = get_destinatario_by_nombre(destinatario)
            
            if not destinatario_existente:
                reply = QMessageBox.question(
                    dialog, 
                    "Destinatario No Registrado",
                    f"El destinatario '{destinatario}' no está registrado en la base de datos.\n\n¿Desea registrarlo ahora?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    nuevo_destinatario = self.mostrar_dialogo_registro_destinatario(dialog, destinatario)
                    if nuevo_destinatario:
                        if insert_destinatario(
                            nuevo_destinatario['nombre'],
                            nuevo_destinatario['direccion'],
                            "",
                            nuevo_destinatario.get('telefono'),
                            nuevo_destinatario.get('email'),
                            nuevo_destinatario.get('notas')
                        ):
                            QMessageBox.information(dialog, "Éxito", "Destinatario registrado correctamente.")
                        else:
                            QMessageBox.warning(dialog, "Error", "No se pudo registrar el destinatario. Puede que ya exista.")
                            return
                    else:
                        return
                else:
                    pass
            
            envios = [
                {
                    "articulo_id": item["articulo_id"],
                    "fecha": fecha,
                    "cantidad": item["cantidad"],
                    "destinatario": destinatario,
                    "metodo_envio": metodo,
                    "costo_lb": costo,
                    "modalidad_cobro": modalidad_db,
                    "peso_cobrado": float(item["cantidad"]) if modalidad == "Pesaje" else 0.0,
                    "largo_cm": largo if modalidad != "Pesaje" else 0.0,
                    "ancho_cm": ancho if modalidad != "Pesaje" else 0.0,
                    "alto_cm": alto if modalidad != "Pesaje" else 0.0,
                    "costo_calculado": costo_calculado / len(self.shipment_items) if len(self.shipment_items) > 0 else costo_calculado,
                    "recibido": recibido,
                    "estado_envio": estado,
                }
                for item in self.shipment_items
            ]
            if insert_envios_batch(envios):
                exitos = len(envios)
                QMessageBox.information(dialog, "Éxito", f"Envío registrado correctamente con {exitos} artículo(s).")
                dialog.accept()
                self.load_data()
                self.notify_refresh()

        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dialog.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        
        main_layout.addLayout(btn_layout)
        
        # Configurar el scroll area con el contenido
        scroll_area.setWidget(content_widget)
        
        # Layout principal del diálogo
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(scroll_area)
        
        dialog.exec()

    def mostrar_dialogo_registro_destinatario(self, parent_dialog, nombre_sugerido):
        """Muestra un diálogo para registrar un nuevo destinatario."""
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("Registrar Nuevo Destinatario")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout()
        
        input_nombre = QLineEdit()
        input_nombre.setText(nombre_sugerido)
        
        input_direccion = QLineEdit()
        input_direccion.setPlaceholderText("Dirección física")
        
        input_telefono = QLineEdit()
        input_telefono.setPlaceholderText("Teléfono (opcional)")
        
        input_email = QLineEdit()
        input_email.setPlaceholderText("Email (opcional)")
        
        input_notas = QLineEdit()
        input_notas.setPlaceholderText("Notas adicionales (opcional)")
        
        layout.addRow("Nombre *:", input_nombre)
        layout.addRow("Dirección *:", input_direccion)
        layout.addRow("Teléfono:", input_telefono)
        layout.addRow("Email:", input_email)
        layout.addRow("Notas:", input_notas)
        
        btn_guardar = QPushButton("Registrar Destinatario")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            nombre = input_nombre.text().strip()
            direccion = input_direccion.text().strip()
            telefono = input_telefono.text().strip() or None
            email = input_email.text().strip() or None
            notas = input_notas.text().strip() or None
            
            if not nombre:
                QMessageBox.warning(dialog, "Error", "El nombre es obligatorio.")
                return
            
            if not direccion:
                QMessageBox.warning(dialog, "Error", "La dirección es obligatoria.")
                return
            
            # Retornar datos del destinatario
            dialog.destinatario_data = {
                'nombre': nombre,
                'direccion': direccion,
                'telefono': telefono,
                'email': email,
                'notas': notas
            }
            dialog.accept()
        
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dialog.reject)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            return getattr(dialog, 'destinatario_data', None)
        return None

    def show_context_menu(self, position):
        """Muestra menú contextual en la tabla de envíos."""
        item = self.table.itemAt(position)
        if not item:
            return

        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item:
            QMessageBox.warning(self, "Error", "Envío no válido")
            return

        envio_ids = id_item.data(Qt.UserRole) or []
        if isinstance(envio_ids, list):
            envio_id = envio_ids[0] if envio_ids else None
        else:
            envio_id = envio_ids
        if not envio_id:
            QMessageBox.warning(self, "Error", "No se pudo identificar el envío")
            return
        
        menu = QMenu(self)
        action_editar = menu.addAction("Editar")
        action_borrar = menu.addAction("Borrar")
        
        action = menu.exec(self.table.mapToGlobal(position))
        
        if action == action_editar:
            self.show_edit_dialog(envio_id)
        elif action == action_borrar:
            self.delete_envio_row(envio_id)

    def show_edit_dialog(self, envio_id):
        """Muestra diálogo para editar un envío existente."""
        envio = get_envio_by_id(envio_id)
        if not envio:
            QMessageBox.critical(self, "Error", "No se encontró el envío.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Envío")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout()
        
        articulos = get_articulos()
        combo_articulo = QComboBox()
        for art in articulos:
            combo_articulo.addItem(f"{art['nombre']}", art['id'])
        
        # Seleccionar el artículo actual
        index = combo_articulo.findData(envio['articulo_id'])
        if index >= 0:
            combo_articulo.setCurrentIndex(index)
        
        input_fecha = QDateEdit()
        input_fecha.setCalendarPopup(True)
        input_fecha.setDate(QDate.fromString(envio['fecha'], "yyyy-MM-dd"))
        
        input_cantidad = QSpinBox()
        input_cantidad.setRange(1, 100000)
        input_cantidad.setValue(envio['cantidad'])
        
        input_destinatario = QLineEdit()
        input_destinatario.setText(envio['destinatario'])
        
        input_metodo = QComboBox()
        input_metodo.addItems(["Aéreo", "Marítimo", "Terrestre", "Courier"])
        index_metodo = input_metodo.findText(envio['metodo_envio'])
        if index_metodo >= 0:
            input_metodo.setCurrentIndex(index_metodo)
        
        # Selector de modalidad de cobro
        combo_modalidad = QComboBox()
        combo_modalidad.addItems(["Pesaje", "Contenedor / Dimensiones"])
        modalidad_actual = envio.get('modalidad_cobro', 'Peso')
        if modalidad_actual == "Contenedor":
            combo_modalidad.setCurrentText("Contenedor / Dimensiones")
        else:
            combo_modalidad.setCurrentText("Pesaje")
        
        input_costo = QDoubleSpinBox()
        input_costo.setRange(0, 1000000)
        input_costo.setValue(envio['costo_lb'])
        input_costo.setPrefix("$")
        input_costo.setSuffix(" USD")
        
        # Campos de dimensiones para contenedor
        input_largo = QDoubleSpinBox()
        input_largo.setRange(0, 5000)
        input_largo.setValue(envio.get('largo_cm', 0.0))
        input_largo.setSuffix(" cm")
        input_largo.setEnabled(modalidad_actual == "Contenedor")
        
        input_ancho = QDoubleSpinBox()
        input_ancho.setRange(0, 5000)
        input_ancho.setValue(envio.get('ancho_cm', 0.0))
        input_ancho.setSuffix(" cm")
        input_ancho.setEnabled(modalidad_actual == "Contenedor")
        
        input_alto = QDoubleSpinBox()
        input_alto.setRange(0, 5000)
        input_alto.setValue(envio.get('alto_cm', 0.0))
        input_alto.setSuffix(" cm")
        input_alto.setEnabled(modalidad_actual == "Contenedor")
        
        combo_estado = QComboBox()
        combo_estado.addItems([
            ShipmentStatus.IN_TRANSIT.value,
            ShipmentStatus.DELIVERED.value,
            ShipmentStatus.RETURNED.value,
            ShipmentStatus.CANCELLED.value,
        ])
        estado_actual = envio.get("estado_envio") or (ShipmentStatus.DELIVERED.value if envio.get("recibido") else ShipmentStatus.IN_TRANSIT.value)
        combo_estado.setCurrentText(estado_actual)
        
        # Contenedor para campos de dimensiones en edición
        dimensiones_container_edit = QWidget()
        dimensiones_layout_edit = QFormLayout(dimensiones_container_edit)
        dimensiones_layout_edit.addRow("Largo:", input_largo)
        dimensiones_layout_edit.addRow("Ancho:", input_ancho)
        dimensiones_layout_edit.addRow("Alto:", input_alto)
        dimensiones_container_edit.setVisible(modalidad_actual == "Contenedor")  # Visible solo si es Contenedor
        
        # Función para manejar cambio de modalidad en edición
        def on_modalidad_changed_edit():
            modalidad = combo_modalidad.currentText()
            if modalidad == "Pesaje":
                input_costo.setPrefix("$")
                input_costo.setSuffix(" USD")
                dimensiones_container_edit.setVisible(False)  # Ocultar dimensiones
            else:  # Contenedor / Dimensiones
                input_costo.setPrefix("$")
                input_costo.setSuffix(" USD (Tarifa Plana)")
                dimensiones_container_edit.setVisible(True)  # Mostrar dimensiones
        
        combo_modalidad.currentTextChanged.connect(on_modalidad_changed_edit)
        
        layout.addRow("Artículo:", combo_articulo)
        layout.addRow("Fecha:", input_fecha)
        layout.addRow("Cantidad:", input_cantidad)
        layout.addRow("Destinatario:", input_destinatario)
        layout.addRow("Método de Envío:", input_metodo)
        layout.addRow("Modalidad de Cobro:", combo_modalidad)
        layout.addRow("Tarifa:", input_costo)
        layout.addRow(dimensiones_container_edit)  # Contenedor de dimensiones
        layout.addRow("Estado:", combo_estado)
        
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            articulo_id = combo_articulo.currentData()
            fecha = input_fecha.date().toString("yyyy-MM-dd")
            cantidad = input_cantidad.value()
            destinatario = input_destinatario.text().strip()
            metodo = input_metodo.currentText()
            modalidad = combo_modalidad.currentText()
            costo = input_costo.value()
            largo = input_largo.value()
            ancho = input_ancho.value()
            alto = input_alto.value()
            estado = combo_estado.currentText()
            recibido = 1 if estado == ShipmentStatus.DELIVERED.value else 0
            
            # Cálculo diferenciado según modalidad de cobro
            costo_calculado = 0.0
            modalidad_db = "Peso"
            
            if modalidad == "Pesaje":
                modalidad_db = "Peso"
                costo_calculado = float(cantidad) * float(costo)
            else:
                modalidad_db = "Contenedor"
                costo_calculado = costo  # Tarifa plana del contenedor

            if not articulo_id:
                QMessageBox.warning(dialog, "Error", "Debe seleccionar un artículo.")
                return

            if not destinatario:
                QMessageBox.warning(dialog, "Error", "El destinatario es obligatorio.")
                return

            if update_envio(
                envio_id, articulo_id, fecha, cantidad, destinatario, metodo, costo,
                recibido, None, modalidad_db, float(cantidad) if modalidad == "Pesaje" else 0.0,
                largo if modalidad != "Pesaje" else 0.0,
                ancho if modalidad != "Pesaje" else 0.0,
                alto if modalidad != "Pesaje" else 0.0,
                costo_calculado, estado
            ):
                QMessageBox.information(dialog, "Éxito", "Envío actualizado correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo actualizar el envío.")
        
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dialog.reject)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        
        dialog.exec()

    def delete_envio_row(self, envio_id):
        """Elimina un envío después de confirmación."""
        reply = QMessageBox.question(
            self, "Confirmar Borrado",
            "¿Está seguro de que desea eliminar este envío?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_envio(envio_id):
                QMessageBox.information(self, "Éxito", "Envío eliminado correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar el envío.")