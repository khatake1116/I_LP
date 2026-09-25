# ui/views/adress_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView,
                               QDialog, QLineEdit, QFormLayout, QMessageBox, QComboBox, QMenu,
                               QAbstractItemView)
from PySide6.QtCore import Qt
from database.models import (get_destinatarios, insert_destinatario, 
                            update_destinatario, delete_destinatario)
from ui.views.base_view import BaseRefreshView

class AdressView(BaseRefreshView):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Controles superiores
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Registrar Destinatario")
        self.btn_add.setObjectName("btn_primario")
        self.btn_add.clicked.connect(self.show_add_dialog)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("Editar seleccionado")
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

        # Configuración de la tabla de destinatarios
        self.table = QTableWidget()
        # Oculta el encabezado vertical
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Dirección", "Teléfono", "Email", "Acción"
        ])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.configure_table_sorting(self.table)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        self.load_data()

    def on_selection_changed(self):
        """Actualiza el estado de los botones cuando cambia la selección."""
        has_selection = self.table.selectionModel().hasSelection()
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def delete_selected(self):
        """Elimina los destinatarios seleccionados."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            QMessageBox.information(self, "Eliminar", "No hay filas seleccionadas.")
            return
        
        destinatario_ids = []
        for row in selected_rows:
            id_item = self.table.item(row, 0)
            if id_item:
                destinatario_ids.append(int(id_item.text()))
        
        if not destinatario_ids:
            QMessageBox.warning(self, "Error", "No se pudieron identificar los destinatarios seleccionados.")
            return
        
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro de eliminar los {len(destinatario_ids)} destinatarios seleccionados? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Eliminar destinatarios uno por uno (delete_destinatario usa soft delete)
            exitos = 0
            for destinatario_id in destinatario_ids:
                if delete_destinatario(destinatario_id):
                    exitos += 1
            
            if exitos > 0:
                QMessageBox.information(self, "Éxito", f"Se eliminaron {exitos} destinatarios correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron eliminar los destinatarios.")

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Editar destinatario", "Selecciona primero una fila.")
            return
        item = self.table.item(row, 0)
        if item:
            self.show_edit_dialog(int(item.data(Qt.UserRole) or item.text()))

    def load_data(self):
        """Carga los destinatarios desde la base de datos sin filtros."""
        destinatarios = get_destinatarios()
        
        self.table.setRowCount(len(destinatarios))
        for row_idx, dest in enumerate(destinatarios):
            id_item = QTableWidgetItem(str(dest['id']))
            id_item.setData(Qt.UserRole, dest['id'])
            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(dest['nombre']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(dest['direccion'] or ""))
            self.table.setItem(row_idx, 3, QTableWidgetItem(dest['telefono'] or ""))
            self.table.setItem(row_idx, 4, QTableWidgetItem(dest['email'] or ""))
            
            # Botón de acción (editar/eliminar)
            btn_action = QPushButton("⋮")
            btn_action.setMaximumWidth(30)
            btn_action.clicked.connect(lambda checked=False, idx=row_idx: self.show_row_menu(idx))
            self.table.setCellWidget(row_idx, 5, btn_action)

    def show_add_dialog(self):
        """Muestra diálogo para registrar un nuevo destinatario."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar Nuevo Destinatario")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout()
        
        input_nombre = QLineEdit()
        input_nombre.setPlaceholderText("Nombre completo del destinatario")
        
        input_direccion = QLineEdit()
        input_direccion.setPlaceholderText("Dirección física")
        
        input_telefono = QLineEdit()
        input_telefono.setPlaceholderText("TeléfonoContacto (opcional)")
        
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
            
            # Pasar parámetros en el orden correcto: nombre, direccion, numero, telefono, email, notas
            if insert_destinatario(nombre, direccion, "", telefono, email, notas):
                QMessageBox.information(dialog, "Éxito", "Destinatario registrado correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.warning(dialog, "Error", "No se pudo registrar el destinatario. Puede que ya exista.")
        
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

    def show_edit_dialog(self, destinatario_id):
        """Muestra diálogo para editar un destinatario existente."""
        destinatarios = get_destinatarios()
        destinatario = None
        for dest in destinatarios:
            if dest['id'] == destinatario_id:
                destinatario = dest
                break
        
        if not destinatario:
            QMessageBox.critical(self, "Error", "No se encontró el destinatario.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Destinatario")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout()
        
        input_nombre = QLineEdit()
        input_nombre.setText(destinatario['nombre'])
        
        input_direccion = QLineEdit()
        input_direccion.setText(destinatario['direccion'] or "")
        
        input_telefono = QLineEdit()
        input_telefono.setText(destinatario['telefono'] or "")
        
        input_email = QLineEdit()
        input_email.setText(destinatario['email'] or "")
        
        input_notas = QLineEdit()
        input_notas.setText(destinatario['notas'] or "")
        
        layout.addRow("Nombre *:", input_nombre)
        layout.addRow("Dirección *:", input_direccion)
        layout.addRow("Teléfono:", input_telefono)
        layout.addRow("Email:", input_email)
        layout.addRow("Notas:", input_notas)
        
        btn_guardar = QPushButton("Guardar Cambios")
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
            
            if update_destinatario(
                destinatario_id,
                nombre,
                direccion,
                numero="",
                telefono=telefono,
                email=email,
                notas=notas
            ):
                QMessageBox.information(dialog, "Éxito", "Destinatario actualizado correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo actualizar el destinatario.")
        
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

    def show_row_menu(self, row_idx):
        """Muestra menú de acciones para una fila específica."""
        id_item = self.table.item(row_idx, 0)
        if not id_item:
            return
        
        destinatario_id = int(id_item.text())
        nombre_item = self.table.item(row_idx, 1)
        nombre = nombre_item.text() if nombre_item else "Destinatario"
        
        menu = QMenu(self)
        action_editar = menu.addAction(f"Editar {nombre}")
        action_borrar = menu.addAction("Eliminar")
        
        # Mostrar menú en la posición del botón
        btn_widget = self.table.cellWidget(row_idx, 5)
        if btn_widget:
            action = menu.exec(btn_widget.mapToGlobal(btn_widget.rect().bottomLeft()))
            
            if action == action_editar:
                self.show_edit_dialog(destinatario_id)
            elif action == action_borrar:
                self.delete_destinatario_row(destinatario_id, nombre)

    def show_context_menu(self, position):
        """Muestra menú contextual con opciones de editar y borrar."""
        item = self.table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        
        # Validación segura del ID
        id_item = self.table.item(row, 0)
        if not id_item or not id_item.text().strip():
            QMessageBox.warning(self, "Error", "ID de destinatario no válido")
            return
        
        try:
            destinatario_id = int(id_item.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "ID debe ser un número entero")
            return
        
        nombre_item = self.table.item(row, 1)
        nombre = nombre_item.text() if nombre_item else "Destinatario"
        
        menu = QMenu(self)
        action_editar = menu.addAction(f"Editar {nombre}")
        action_borrar = menu.addAction("Eliminar")
        
        action = menu.exec(self.table.mapToGlobal(position))
        
        if action == action_editar:
            self.show_edit_dialog(destinatario_id)
        elif action == action_borrar:
            self.delete_destinatario_row(destinatario_id, nombre)

    def delete_destinatario_row(self, destinatario_id, nombre):
        """Elimina un destinatario después de confirmación."""
        reply = QMessageBox.question(
            self, "Confirmar Borrado",
            f"¿Está seguro de que desea eliminar el destinatario '{nombre}'?\n\n"
            "Nota: Esto no afectará los envíos existentes que ya tienen este destinatario.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_destinatario(destinatario_id):
                QMessageBox.information(self, "Éxito", "Destinatario eliminado correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar el destinatario.")