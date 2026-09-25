# ui/dialogs/category_dialog.py
# Diálogo de gestión de categorías para ILP
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QListWidget, QMessageBox,
                               QInputDialog, QFrame)
from PySide6.QtCore import Qt
from database.categories import get_categorias, crear_categoria, actualizar_categoria, eliminar_categoria, CATEGORIAS_POR_DEFECTO
import logging

logger = logging.getLogger(__name__)

class CategoryDialog(QDialog):
    """Diálogo modal para gestión de categorías."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Categorías disponibles")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
        self.load_categories()
    
    def setup_ui(self):
        """Configura la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Título
        title_label = QLabel("Categorías disponibles")
        title_label.setObjectName("CategoryTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtítulo / Instrucción
        subtitle_label = QLabel("Si no encuentras la tuya, agrégala o puedes editar las existentes.")
        subtitle_label.setObjectName("CategorySubtitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("CategorySeparator")
        layout.addWidget(separator)
        
        # Lista de categorías
        self.category_list = QListWidget()
        self.category_list.setObjectName("CategoryList")
        self.category_list.itemDoubleClicked.connect(self.edit_category)
        layout.addWidget(self.category_list)
        
        # Campo de texto para nueva categoría
        input_layout = QHBoxLayout()
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Nombre de nueva categoría...")
        self.category_input.setObjectName("CategoryInput")
        input_layout.addWidget(self.category_input)
        
        btn_add = QPushButton("Agregar")
        btn_add.setObjectName("btn_guardar")
        btn_add.clicked.connect(self.add_category)
        input_layout.addWidget(btn_add)
        
        layout.addLayout(input_layout)
        
        # Botones de acción inferiores
        button_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Editar Seleccionada")
        btn_edit.setObjectName("btn_guardar")
        btn_edit.clicked.connect(self.edit_category)
        button_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Eliminar Seleccionada")
        btn_delete.setObjectName("btn_cancelar")
        btn_delete.clicked.connect(self.delete_category)
        button_layout.addWidget(btn_delete)
        
        button_layout.addStretch()
        
        btn_close = QPushButton("Cerrar")
        btn_close.setObjectName("btn_cancelar")
        btn_close.clicked.connect(self.accept)
        button_layout.addWidget(btn_close)
        
        layout.addLayout(button_layout)
    
    def load_categories(self):
        """Carga las categorías en la lista, precargando las categorías por defecto si es necesario."""
        try:
            categorias = get_categorias()
            self.category_list.clear()
            self.category_list.addItems(categorias)
            
            # Si la lista está vacía (primer uso), precargar categorías por defecto
            if not categorias:
                self.initialize_default_categories()
        except Exception as e:
            logger.error(f"Error al cargar categorías: {e}")
            QMessageBox.critical(self, "Error", f"No se pudieron cargar las categorías: {e}")
    
    def initialize_default_categories(self):
        """Inicializa las categorías por defecto del sistema."""
        try:
            for categoria in CATEGORIAS_POR_DEFECTO:
                crear_categoria(categoria)
            self.load_categories()
        except Exception as e:
            logger.error(f"Error al inicializar categorías por defecto: {e}")
    
    def add_category(self):
        """Agrega una nueva categoría."""
        nombre = self.category_input.text().strip()
        
        if not nombre:
            QMessageBox.warning(self, "Advertencia", "El nombre de la categoría no puede estar vacío.")
            return
        
        if len(nombre) > 50:
            QMessageBox.warning(self, "Advertencia", "El nombre de la categoría no puede exceder 50 caracteres.")
            return
        
        success, message = crear_categoria(nombre)
        
        if success:
            QMessageBox.information(self, "Éxito", message)
            self.category_input.clear()
            self.load_categories()
        else:
            QMessageBox.warning(self, "Error", message)
    
    def edit_category(self):
        """Edita la categoría seleccionada."""
        current_item = self.category_list.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Advertencia", "Selecciona una categoría para editar.")
            return
        
        nombre_anterior = current_item.text()
        
        # Diálogo para ingresar nuevo nombre
        nuevo_nombre, ok = QInputDialog.getText(
            self, 
            "Editar Categoría",
            f"Nuevo nombre para '{nombre_anterior}':",
            text=nombre_anterior
        )
        
        if ok and nuevo_nombre.strip():
            nuevo_nombre = nuevo_nombre.strip()
            
            if len(nuevo_nombre) > 50:
                QMessageBox.warning(self, "Advertencia", "El nombre no puede exceder 50 caracteres.")
                return
            
            success, message = actualizar_categoria(nombre_anterior, nuevo_nombre)
            
            if success:
                QMessageBox.information(self, "Éxito", message)
                self.load_categories()
            else:
                QMessageBox.warning(self, "Error", message)
    
    def delete_category(self):
        """Elimina la categoría seleccionada."""
        current_item = self.category_list.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Advertencia", "Selecciona una categoría para eliminar.")
            return
        
        nombre = current_item.text()
        
        # Confirmación
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar la categoría '{nombre}'?\n\n"
            "Los artículos con esta categoría serán cambiados a 'General'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = eliminar_categoria(nombre)
            
            if success:
                QMessageBox.information(self, "Éxito", message)
                self.load_categories()
            else:
                QMessageBox.warning(self, "Error", message)