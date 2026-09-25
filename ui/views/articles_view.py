# ui/views/articles_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView,
                             QDialog, QFormLayout, QMessageBox, QLineEdit,
                             QDoubleSpinBox, QComboBox, QMenu, QLabel,
                             QAbstractItemView)
from PySide6.QtCore import Qt
from database.models import get_articulos, get_articulo_by_id, insert_articulo, update_articulo, delete_articulo
from database.categories import get_categorias
from ui.views.base_view import BaseRefreshView
from ui.dialogs.category_dialog import CategoryDialog
from core.formatting import format_custom_number

class ArticlesView(BaseRefreshView):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Controles superiores
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Nuevo Artículo")
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
        
        self.btn_categories = QPushButton("Categorías")
        self.btn_categories.setObjectName("btn_guardar")
        self.btn_categories.clicked.connect(self.show_categories_dialog)
        btn_layout.addWidget(self.btn_categories)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Configuración de la tabla de Artículos
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Nombre del Artículo", "Categoría", "Descripción", "Peso Base (lb)"
        ])
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
        """Elimina los artículos seleccionados."""
        selected_rows = [index.row() for index in self.table.selectionModel().selectedRows()]
        if not selected_rows:
            QMessageBox.information(self, "Eliminar", "No hay filas seleccionadas.")
            return
        
        articulo_ids = []
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                articulo_ids.append(item.data(Qt.UserRole))
        
        if not articulo_ids:
            QMessageBox.warning(self, "Error", "No se pudieron identificar los artículos seleccionados.")
            return
        
        reply = QMessageBox.warning(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro de eliminar los {len(articulo_ids)} artículos seleccionados? Esta acción no se puede deshacer.\n\n"
            "Nota: Los artículos con historial de compras o envíos no podrán ser eliminados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            exitos = 0
            for articulo_id in articulo_ids:
                if delete_articulo(articulo_id):
                    exitos += 1
            
            if exitos > 0:
                QMessageBox.information(self, "Éxito", f"Se eliminaron {exitos} artículos correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudieron eliminar los artículos. Es posible que tengan historial asociado.")

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Editar artículo", "Selecciona primero una fila.")
            return
        item = self.table.item(row, 0)
        if item:
            self.show_edit_dialog(item.data(Qt.UserRole))

    def load_data(self):
        """Carga los artículos directamente desde la tabla base."""
        articulos = get_articulos()
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(articulos))
        for row_idx, art in enumerate(articulos):
            articulo_id = art['id']
            item_nombre = QTableWidgetItem(str(art['nombre']))
            item_nombre.setData(Qt.UserRole, articulo_id)
            item_categoria = QTableWidgetItem(str(art['categoria']))
            item_categoria.setData(Qt.UserRole, articulo_id)
            item_descripcion = QTableWidgetItem(str(art.get('descripcion', '')))
            item_descripcion.setData(Qt.UserRole, articulo_id)
            item_peso = QTableWidgetItem(f"{format_custom_number(float(art['peso_lb']))} lb")
            item_peso.setData(Qt.UserRole, articulo_id)

            self.table.setItem(row_idx, 0, item_nombre)
            self.table.setItem(row_idx, 1, item_categoria)
            self.table.setItem(row_idx, 2, item_descripcion)
            self.table.setItem(row_idx, 3, item_peso)
        self.table.setSortingEnabled(True)

    def show_add_dialog(self):
        """Diálogo para registrar un nuevo artículo en el catálogo."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrar Nuevo Artículo")
        dialog.setMinimumWidth(400)
        
        form_layout = QFormLayout()
        
        input_nombre = QLineEdit()
        input_nombre.setPlaceholderText("Ej. Laptop Core i3, Zapatillas...")

        categorias = get_categorias()
        input_categoria = QComboBox()
        input_categoria.setEditable(True)
        input_categoria.addItems(categorias)

        input_descripcion = QLineEdit()
        input_descripcion.setPlaceholderText("Descripción breve del artículo")

        input_peso = QDoubleSpinBox()
        input_peso.setRange(0.0, 1000.0)
        input_peso.setValue(0.0)
        input_peso.setSuffix(" lb")
        input_peso.setDecimals(3)
        
        form_layout.addRow("Nombre:", input_nombre)
        form_layout.addRow("Categoría:", input_categoria)
        form_layout.addRow("Descripción:", input_descripcion)
        form_layout.addRow("Peso Base:", input_peso)
        
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            nombre = input_nombre.text().strip()
            categoria = input_categoria.currentText().strip() or "General"
            peso = input_peso.value()
            descripcion = input_descripcion.text().strip()
            
            if not nombre:
                QMessageBox.warning(dialog, "Error", "El nombre del artículo no puede estar vacío.")
                return
            
            articulo_id = insert_articulo(nombre, categoria, peso, descripcion)
            if articulo_id is not None:
                QMessageBox.information(dialog, "Éxito", "Artículo agregado al catálogo correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo guardar. Es posible que el nombre ya exista.")
        
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

    def show_categories_dialog(self):
        """Muestra el diálogo de gestión de categorías."""
        dialog = CategoryDialog(self)
        dialog.exec()
        # Recargar la vista para actualizar las categorías en el combobox
        self.load_data()
        self.notify_refresh()

    def show_context_menu(self, position):
        """Menú contextual para Editar o Borrar un artículo del catálogo."""
        item = self.table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item:
            QMessageBox.warning(self, "Error", "Artículo no válido")
            return

        articulo_id = id_item.data(Qt.UserRole)
        if not articulo_id:
            QMessageBox.warning(self, "Error", "No se pudo identificar el artículo")
            return
        
        menu = QMenu(self)
        action_editar = menu.addAction("Editar Artículo")
        action_borrar = menu.addAction("Eliminar del Catálogo")
        
        action = menu.exec(self.table.mapToGlobal(position))
        
        if action == action_editar:
            self.show_edit_dialog(articulo_id)
        elif action == action_borrar:
            self.delete_article_row(articulo_id)

    def show_edit_dialog(self, articulo_id):
        """Diálogo para editar un artículo existente."""
        art = get_articulo_by_id(articulo_id)
        if not art:
            QMessageBox.critical(self, "Error", "No se encontró el artículo.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Artículo")
        dialog.setMinimumWidth(400)
        
        form_layout = QFormLayout()
        
        input_nombre = QLineEdit(art['nombre'])

        categorias = get_categorias()
        input_categoria = QComboBox()
        input_categoria.setEditable(True)
        input_categoria.addItems(categorias)
        input_categoria.setCurrentText(art['categoria'])

        input_descripcion = QLineEdit(str(art.get('descripcion', '')))

        input_peso = QDoubleSpinBox()
        input_peso.setRange(0.0, 1000.0)
        input_peso.setValue(float(art['peso_lb']))
        input_peso.setSuffix(" lb")
        input_peso.setDecimals(3)
        
        form_layout.addRow("Nombre:", input_nombre)
        form_layout.addRow("Categoría:", input_categoria)
        form_layout.addRow("Descripción:", input_descripcion)
        form_layout.addRow("Peso Base:", input_peso)
        
        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setObjectName("btn_guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        
        def guardar():
            nombre = input_nombre.text().strip()
            categoria = input_categoria.currentText().strip() or "General"
            peso = input_peso.value()
            descripcion = input_descripcion.text().strip()
            
            if not nombre:
                QMessageBox.warning(dialog, "Error", "El nombre no puede estar vacío.")
                return
            
            if update_articulo(articulo_id, nombre, categoria, peso, descripcion):
                QMessageBox.information(dialog, "Éxito", "Artículo actualizado correctamente.")
                dialog.accept()
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(dialog, "Error", "No se pudo actualizar el artículo.")
        
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

    def delete_article_row(self, articulo_id):
        """Elimina un artículo tras confirmación (afectará en cascada a compras/envíos si aplica)."""
        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            "¿Estás seguro de realizar esta acción?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Eliminar directamente sin undo/redo
            if delete_articulo(articulo_id):
                QMessageBox.information(self, "Éxito", "Artículo eliminado correctamente.")
                self.load_data()
                self.notify_refresh()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar el artículo.")

