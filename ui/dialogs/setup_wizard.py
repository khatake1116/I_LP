# ui/dialogs/setup_wizard.py
import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout, QLabel, QLineEdit,
    QWizard, QWizardPage, QComboBox, QMessageBox
)

from core.paths import get_config_path
from database.models import init_db


class SetupWizardDialog(QWizard):
    """Asistente inicial para configurar el perfil comercial y la base local."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración inicial")
        self.setMinimumSize(560, 420)
        self.setWizardStyle(QWizard.ModernStyle)

        self.identity_page = self.create_identity_page()
        self.currency_page = self.create_currency_page()
        self.modules_page = self.create_modules_page()
        self.addPage(self.identity_page)
        self.addPage(self.currency_page)
        self.addPage(self.modules_page)

    def create_identity_page(self):
        page = QWizardPage()
        page.setTitle("Perfil del negocio")
        page.setSubTitle("Registra la identidad que aparecerá en el encabezado.")
        layout = QFormLayout(page)

        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("Ej. Inventario Duniel")
        self.branch_input = QLineEdit()
        self.branch_input.setPlaceholderText("Ej. Sucursal principal")
        self.logo_path = ""
        self.logo_preview = QLabel("Sin logo seleccionado")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setMinimumHeight(80)
        logo_button = self.create_button("Seleccionar logo o avatar", self.select_logo)

        layout.addRow("Empresa / negocio:", self.company_input)
        layout.addRow("Sucursal principal:", self.branch_input)
        layout.addRow(self.logo_preview)
        layout.addRow(logo_button)
        return page

    def create_currency_page(self):
        page = QWizardPage()
        page.setTitle("Moneda base")
        page.setSubTitle("Define la moneda utilizada para mostrar los importes.")
        layout = QFormLayout(page)

        self.currency_input = QComboBox()
        self.currency_input.addItems(["CUP", "USD"])
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.0001, 999999999)
        self.rate_input.setDecimals(4)
        self.rate_input.setValue(1.0)
        self.rate_input.setSuffix(" CUP por USD")
        layout.addRow("Moneda base:", self.currency_input)
        layout.addRow("Tasa de cambio inicial:", self.rate_input)
        return page

    def create_modules_page(self):
        page = QWizardPage()
        page.setTitle("Módulos activos")
        page.setSubTitle("Selecciona las áreas que estarán disponibles en el menú.")
        layout = QFormLayout(page)
        self.module_checks = {}
        for key, label in (
            ("inventario", "Inventario"),
            ("compras", "Compras"),
            ("ventas", "Ventas / POS"),
            ("logistica", "Logística"),
        ):
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.module_checks[key] = checkbox
            layout.addRow(checkbox)
        return page

    @staticmethod
    def create_button(text, handler):
        from PySide6.QtWidgets import QPushButton
        button = QPushButton(text)
        button.clicked.connect(handler)
        return button

    def select_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar logo o avatar", "", "Imágenes (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Logo no válido", "No se pudo cargar la imagen seleccionada.")
            return
        self.logo_path = path
        self.logo_preview.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def accept(self):
        if not self.company_input.text().strip() or not self.branch_input.text().strip():
            QMessageBox.warning(self, "Datos incompletos", "Indica el nombre de la empresa y la sucursal.")
            return

        config = {
            "theme": "dark",
            "empresa": self.company_input.text().strip(),
            "sucursal": self.branch_input.text().strip(),
            "moneda": self.currency_input.currentText(),
            "tasa_cambio": self.rate_input.value(),
            "modulos_activos": {
                key: checkbox.isChecked() for key, checkbox in self.module_checks.items()
            },
            "db_setup_prompt_done": True,
        }
        if self.logo_path:
            destination = get_config_path().parent / ("logo_empresa" + Path(self.logo_path).suffix)
            try:
                shutil.copy2(self.logo_path, destination)
                config["logo"] = str(destination)
            except OSError:
                config["logo"] = self.logo_path
        try:
            with get_config_path().open("w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2, ensure_ascii=False)
            init_db()
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Error de configuración", f"No se pudo guardar la configuración: {error}")
            return
        super().accept()