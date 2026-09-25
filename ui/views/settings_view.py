# ui/views/settings_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget,
                               QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView,
                               QLabel, QSpinBox, QGroupBox, QFormLayout, QFrame,
                               QMessageBox, QFileDialog, QLineEdit, QComboBox,
                               QDoubleSpinBox, QScrollArea, QTabWidget, QStackedWidget)
from PySide6.QtCore import Qt, Signal
import json
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime
from core.paths import get_config_path, save_theme
from core.theme import load_theme_qss
from database.connection import DB_PATH
from database.models import init_db
from ui.views.base_view import BaseRefreshView

CONFIG_FILE = get_config_path()

class SettingsView(BaseRefreshView):
    profile_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 8, 4)
        layout.setSpacing(12)
        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

        profile_group = QGroupBox("Perfil de la sucursal")
        profile_group.setObjectName("SettingsGroup")
        profile_layout = QFormLayout(profile_group)
        self.profile_company = QLineEdit()
        self.profile_branch = QLineEdit()
        self.profile_user = QLineEdit()
        self.profile_logo = QLineEdit()
        self.profile_logo.setReadOnly(True)
        btn_logo = QPushButton("Seleccionar logo")
        btn_logo.clicked.connect(self.select_profile_logo)
        logo_row = QHBoxLayout()
        logo_row.addWidget(self.profile_logo)
        logo_row.addWidget(btn_logo)
        self.profile_currency = QComboBox()
        self.profile_currency.addItems(["CUP", "USD"])
        self.profile_rate = QDoubleSpinBox()
        self.profile_rate.setRange(0.0001, 999999999)
        self.profile_rate.setDecimals(2)
        self.profile_rate.setSuffix(" CUP/USD")
        profile_layout.addRow("Empresa / negocio:", self.profile_company)
        profile_layout.addRow("Sucursal:", self.profile_branch)
        profile_layout.addRow("Usuario responsable:", self.profile_user)
        profile_layout.addRow("Logo / avatar:", logo_row)
        profile_layout.addRow("Moneda base:", self.profile_currency)
        profile_layout.addRow("Tasa de cambio:", self.profile_rate)
        btn_save_profile = QPushButton("Guardar perfil y moneda")
        btn_save_profile.setObjectName("btn_guardar")
        btn_save_profile.clicked.connect(self.save_profile_config)
        profile_layout.addRow(btn_save_profile)
        layout.addWidget(profile_group)

        # --- GESTOR DE ALERTAS ---
        alerts_group = QGroupBox("Gestor de Alertas")
        alerts_group.setObjectName("SettingsGroup")
        alerts_layout = QFormLayout(alerts_group)
        
        self.spin_dias_compras = QSpinBox()
        self.spin_dias_compras.setRange(1, 90)
        self.spin_dias_compras.setValue(7)
        self.spin_dias_compras.setSuffix(" días")
        self.spin_dias_compras.setToolTip("Días límite para alertar sobre compras pendientes")
        
        self.spin_dias_envios = QSpinBox()
        self.spin_dias_envios.setRange(1, 90)
        self.spin_dias_envios.setValue(15)
        self.spin_dias_envios.setSuffix(" días")
        self.spin_dias_envios.setToolTip("Días límite para alertar sobre envíos en tránsito")
        
        alerts_layout.addRow("Alertar compras pendientes después de:", self.spin_dias_compras)
        alerts_layout.addRow("Alertar envíos en tránsito después de:", self.spin_dias_envios)
        
        btn_save_alerts = QPushButton("Guardar Configuración de Alertas")
        btn_save_alerts.setObjectName("btn_guardar")
        btn_save_alerts.clicked.connect(self.save_alerts_config)
        alerts_layout.addRow(btn_save_alerts)
        
        layout.addWidget(alerts_group)

        backup_layout = QHBoxLayout()
        btn_export = QPushButton("Exportar Respaldo (.ilp)")
        btn_export.setObjectName("btn_guardar")
        btn_export.clicked.connect(self.export_database)
        btn_import = QPushButton("Cargar Base de Datos (.ilp)")
        btn_import.setObjectName("btn_primario")
        btn_import.clicked.connect(self.import_database)
        btn_reset = QPushButton("Resetear Base de Datos")
        btn_reset.setObjectName("btn_cancelar")
        btn_reset.clicked.connect(self.reset_database)
        backup_layout.addWidget(btn_export)
        backup_layout.addWidget(btn_import)
        backup_layout.addWidget(btn_reset)
        layout.addLayout(backup_layout)

        # --- SWITCH DE TEMA ---
        theme_group = QGroupBox("Apariencia")
        theme_group.setObjectName("SettingsGroup")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_label = QLabel("Tema de la Interfaz")
        theme_label.setObjectName("SettingsLabel")
        theme_layout.addWidget(theme_label)
        
        theme_buttons_layout = QHBoxLayout()
        
        self.btn_dark_theme = QPushButton("🌙 Tema Oscuro")
        self.btn_dark_theme.setCheckable(True)
        self.btn_dark_theme.setChecked(True)
        self.btn_dark_theme.setObjectName("ThemeButton")
        self.btn_dark_theme.clicked.connect(lambda: self.change_theme("dark"))
        
        self.btn_light_theme = QPushButton("☀️ Tema Claro")
        self.btn_light_theme.setCheckable(True)
        self.btn_light_theme.setObjectName("ThemeButton")
        self.btn_light_theme.clicked.connect(lambda: self.change_theme("light"))
        
        theme_buttons_layout.addWidget(self.btn_dark_theme)
        theme_buttons_layout.addWidget(self.btn_light_theme)
        theme_layout.addLayout(theme_buttons_layout)
        
        layout.addWidget(theme_group)
        
        # --- INFORMACIÓN DEL SISTEMA ---
        info_group = QGroupBox("Información del Sistema")
        info_group.setObjectName("SettingsGroup")
        info_layout = QVBoxLayout(info_group)
        
        info_label = QLabel("Inventario de Logística Profesional (ILP)\nVersión 2.2.0 - Mike Dev Inc.\n\nSistema de gestión de inventario con seguimiento de compras, envíos y alertas automáticas.")
        info_label.setObjectName("SettingsInfo")
        info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        self.load_data()

    def load_data(self):
        """Carga la configuración actual desde config.json."""
        config = {}
        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
                    config = json.load(config_file)
        except (OSError, json.JSONDecodeError):
            config = {}

        self.spin_dias_compras.setValue(config.get("dias_alerta_compras", 7))
        self.spin_dias_envios.setValue(config.get("dias_alerta_envios", 15))
        self.profile_company.setText(config.get("empresa", ""))
        self.profile_branch.setText(config.get("sucursal", ""))
        self.profile_user.setText(config.get("usuario", "Sistema"))
        self.profile_logo.setText(config.get("logo", ""))
        self.profile_currency.setCurrentText(config.get("moneda", "CUP"))
        self.profile_rate.setValue(float(config.get("tasa_cambio", 1.0)))

        # Sincronizar estado visual de los botones de tema
        current_theme = config.get("theme", "dark")
        self.btn_dark_theme.setChecked(current_theme == "dark")
        self.btn_light_theme.setChecked(current_theme == "light")

    def select_profile_logo(self):
        logo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar logo o avatar", "", "Imágenes (*.png *.jpg *.jpeg *.bmp)"
        )
        if logo:
            self.profile_logo.setText(logo)

    def save_profile_config(self):
        company = self.profile_company.text().strip()
        branch = self.profile_branch.text().strip()
        if not company or not branch:
            QMessageBox.warning(self, "Perfil incompleto", "Indica la empresa y la sucursal.")
            return
        config = {}
        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
                    config = json.load(config_file)
            config.update({
                "empresa": company,
                "sucursal": branch,
                "usuario": self.profile_user.text().strip() or "Sistema",
                "logo": self.profile_logo.text().strip(),
                "moneda": self.profile_currency.currentText(),
                "tasa_cambio": self.profile_rate.value(),
            })
            with CONFIG_FILE.open("w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2, ensure_ascii=False)
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el perfil: {error}")
            return
        self.profile_updated.emit(config)
        QMessageBox.information(self, "Perfil actualizado", "El perfil y la moneda se actualizaron correctamente.")

    def save_alerts_config(self):
        """Guarda la configuración de alertas."""
        dias_compras = self.spin_dias_compras.value()
        dias_envios = self.spin_dias_envios.value()
        
        config = {}
        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
                    config = json.load(config_file)
            config["dias_alerta_compras"] = dias_compras
            config["dias_alerta_envios"] = dias_envios
            with CONFIG_FILE.open("w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2)
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la configuración: {error}")
            return

        QMessageBox.information(
            self,
            "Configuración Guardada",
            f"Configuración de alertas guardada:\n"
            f"- Compras pendientes: {dias_compras} días\n"
            f"- Envíos en tránsito: {dias_envios} días"
        )

    def _checkpoint_database(self):
        """Cierra la conexión usada para consolidar el WAL antes de copiar."""
        if not DB_PATH.exists():
            return
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()

    def _database_sidecars(self):
        """Devuelve los archivos laterales asociados a la base SQLite."""
        return [Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")]

    def _backup_database(self, label="respaldo"):
        """Genera una copia segura de la base actual antes de reemplazarla."""
        if not DB_PATH.exists():
            return None

        backup_dir = DB_PATH.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_base = backup_dir / f"inventario_{label}_{timestamp}"
        backup_file = backup_base.with_suffix(".ilp")

        try:
            self._checkpoint_database()
            shutil.copy2(DB_PATH, backup_file)
            for sidecar in self._database_sidecars():
                if sidecar.exists():
                    shutil.copy2(sidecar, backup_base.with_name(f"{backup_base.name}{sidecar.suffix}"))
            return backup_file
        except (OSError, sqlite3.Error):
            if backup_file.exists():
                backup_file.unlink()
            raise

    def _restore_backup(self, backup_file):
        """Restaura la base actual desde un respaldo previo si algo falla."""
        if not backup_file or not backup_file.exists():
            return False

        try:
            self._checkpoint_database()
            if DB_PATH.exists():
                DB_PATH.unlink()
            for sidecar in self._database_sidecars():
                if sidecar.exists():
                    sidecar.unlink()

            shutil.copy2(backup_file, DB_PATH)
            backup_name = backup_file.name
            for suffix in ("-wal", "-shm"):
                sidecar_backup = backup_file.with_name(f"{backup_file.stem}{suffix}")
                if sidecar_backup.exists():
                    shutil.copy2(sidecar_backup, Path(f"{DB_PATH}{suffix}"))
            init_db()
            return True
        except (OSError, sqlite3.Error):
            return False

    def export_database(self):
        """Exporta la base activa a un archivo ILP."""
        if not DB_PATH.exists():
            QMessageBox.warning(self, "Respaldo", "No existe una base de datos activa para exportar.")
            return

        destination, _ = QFileDialog.getSaveFileName(
            self, "Exportar Respaldo", "inventario.ilp", "Archivos ILP (*.ilp)"
        )
        if not destination:
            return
        destination = Path(destination)
        if destination.suffix.lower() != ".ilp":
            destination = destination.with_suffix(".ilp")

        try:
            self._checkpoint_database()
            shutil.copyfile(DB_PATH, destination)
            QMessageBox.information(self, "Respaldo", f"Respaldo exportado correctamente en:\n{destination}")
        except (OSError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el respaldo: {error}")

    def _validate_database_file(self, source):
        """Valida integridad y tablas mínimas de un archivo ILP externo."""
        uri = f"file:{source.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {"articulos", "compras", "envios"}
            return integrity == "ok" and required.issubset(tables)
        finally:
            conn.close()

    def import_database(self):
        """Valida y reemplaza la base activa con un archivo ILP seleccionado de forma segura."""
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Cargar Base de Datos", "", "Archivos ILP (*.ilp)"
        )
        if not source_name:
            return

        source = Path(source_name)
        if source.resolve() == DB_PATH.resolve():
            QMessageBox.warning(self, "Carga de base de datos", "El archivo seleccionado ya es la base activa.")
            return

        backup_file = None
        try:
            if not self._validate_database_file(source):
                QMessageBox.critical(
                    self,
                    "Base no válida",
                    "El archivo no supera la validación o no contiene las tablas esenciales: "
                    "articulos, compras y envios."
                )
                return

            backup_file = self._backup_database("antes_carga")
            self._checkpoint_database()
            for sidecar in self._database_sidecars():
                if sidecar.exists():
                    sidecar.unlink()

            if DB_PATH.exists():
                DB_PATH.unlink()
            shutil.copy2(source, DB_PATH)
            init_db()
            self._refresh_application_views()
            QMessageBox.information(
                self,
                "Carga completada",
                f"La base de datos se cargó correctamente.\n\nCopia de seguridad creada en:\n{backup_file}"
            )
        except (OSError, sqlite3.Error) as error:
            if backup_file and self._restore_backup(backup_file):
                QMessageBox.warning(
                    self,
                    "Carga interrumpida",
                    "La carga falló y se restauró la base de datos anterior.\n\nSe recomienda exportar una copia antes de reemplazar la base."
                )
            else:
                QMessageBox.critical(self, "Error", f"No se pudo cargar la base de datos: {error}")

    def reset_database(self):
        """Reinicia la base completa con confirmación de seguridad y sugerencia de respaldo."""
        warning_text = (
            "¿Está seguro de que desea reiniciar la base completa?\n\n"
            "Esta acción elimina todos los datos actuales y crea una nueva base vacía.\n\n"
            "Para evitar pérdidas, primero haga una copia de seguridad desde:\n"
            "Configuración > Exportar Respaldo (.ilp)"
        )
        confirm = QMessageBox.question(
            self,
            "Resetear base de datos",
            warning_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        backup_file = None
        try:
            backup_file = self._backup_database("antes_reset")
            self._checkpoint_database()
            for sidecar in self._database_sidecars():
                if sidecar.exists():
                    sidecar.unlink()
            if DB_PATH.exists():
                DB_PATH.unlink()
            init_db()
            self._refresh_application_views()
            QMessageBox.information(
                self,
                "Base reiniciada",
                f"La base de datos se ha reiniciado correctamente.\n\nCopia de seguridad creada en:\n{backup_file}"
            )
        except (OSError, sqlite3.Error) as error:
            if backup_file and self._restore_backup(backup_file):
                QMessageBox.warning(
                    self,
                    "Reset interrumpido",
                    "El reinicio falló y se restauró la base anterior.\n\nSe recomienda hacer una copia de seguridad antes de continuar."
                )
            else:
                QMessageBox.critical(self, "Error", f"No se pudo reiniciar la base de datos: {error}")

    def _refresh_application_views(self):
        """Actualiza las vistas existentes después de reemplazar la base, incluso dentro de pestañas anidadas."""
        main_window = self.window()
        seen = set()

        def visit(widget):
            if widget is None or id(widget) in seen:
                return
            seen.add(id(widget))

            if hasattr(widget, "load_data"):
                try:
                    widget.load_data()
                except Exception:
                    pass
            elif hasattr(widget, "load_alerts"):
                try:
                    widget.load_alerts()
                except Exception:
                    pass

            if isinstance(widget, QTabWidget):
                for index in range(widget.count()):
                    visit(widget.widget(index))
            elif isinstance(widget, QStackedWidget):
                for index in range(widget.count()):
                    visit(widget.widget(index))

        stack = getattr(main_window, "stack", None)
        if stack is not None:
            for index in range(stack.count()):
                visit(stack.widget(index))

        if hasattr(main_window, "check_alerts"):
            main_window.check_alerts()

    def change_theme(self, theme):
        """Cambia el tema de la aplicación entre claro y oscuro."""
        from PySide6.QtWidgets import QApplication
        from core.paths import save_theme
        
        if theme == "dark":
            self.btn_dark_theme.setChecked(True)
            self.btn_light_theme.setChecked(False)
        else:
            self.btn_dark_theme.setChecked(False)
            self.btn_light_theme.setChecked(True)
        
        # Cargar QSS completo del tema (base + componentes)
        theme_qss = load_theme_qss(theme)
        if theme_qss:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(theme_qss)
            
            main_window = self.window()
            if hasattr(main_window, "update_nav_icons"):
                main_window.update_nav_icons(theme)
                
            # Guardar el tema seleccionado usando la función centralizada
            save_theme(theme)
