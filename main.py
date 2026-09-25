# main.py
"""
Punto de entrada principal de ILP.

Responsabilidades:
- Inicializar QApplication.
- Configurar icono.
- Aplicar el tema guardado.
- Mostrar SplashScreen.
- Ejecutar configuración inicial.
- Inicializar la base de datos.
- Crear y mostrar MainWindow.

La gestión de rutas pertenece a core.paths.
La gestión de temas pertenece a core.theme.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.paths import (
    get_config_path,
    get_database_path,
    get_ui_assets_path,
    get_saved_theme,
    should_skip_db_setup_prompt,
    mark_db_setup_prompt_done,
)

from core.theme import load_theme_qss

from database.connection import DB_PATH
from database.models import init_db
from ui.dialogs.setup_wizard import SetupWizardDialog
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

DEFAULT_THEME = "dark"
VALID_THEMES = {"dark", "light"}


# ==========================================================
# BASE DE DATOS
# ==========================================================

def validate_database_file(file_path: str | Path) -> bool:
    """
    Valida que un archivo .ilp exista y contenga
    la estructura mínima requerida por la aplicación.
    """
    source = Path(file_path)

    if not source.is_file():
        return False

    try:
        # SQLite en modo solo lectura.
        uri = f"file:{source.resolve().as_posix()}?mode=ro"

        conn = sqlite3.connect(uri, uri=True)

        try:
            integrity = conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            tables = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

            required_tables = {
                "articulos",
                "compras",
                "envios",
            }

            return (
                integrity == "ok"
                and required_tables.issubset(tables)
            )

        finally:
            conn.close()

    except (sqlite3.Error, OSError):
        return False


def prompt_initial_db_setup() -> None:
    """
    Pregunta una sola vez si el usuario desea importar
    una base .ilp existente o crear una nueva.
    """
    if should_skip_db_setup_prompt():
        return

    dialog = QDialog()
    dialog.setWindowTitle("Base de datos inicial")
    dialog.setModal(True)
    dialog.setMinimumWidth(480)

    layout = QVBoxLayout(dialog)

    title = QLabel("¿Ya tienes una base de datos .ilp?")
    title.setStyleSheet(
        "font-size: 15px; font-weight: bold;"
    )

    layout.addWidget(title)

    description = QLabel(
        "Si ya cuentas con una base existente, puedes "
        "importarla ahora.\n"
        "Si no, se creará una base nueva para comenzar "
        "desde cero."
    )

    description.setWordWrap(True)
    layout.addWidget(description)

    btn_import = QPushButton("Sí, importar .ilp")
    btn_import.setObjectName("btn_primario")

    btn_new = QPushButton("No tengo .ilp aún")
    btn_new.setObjectName("btn_guardar")

    # ------------------------------------------------------
    # Importar base existente
    # ------------------------------------------------------

    def import_existing_db() -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            dialog,
            "Selecciona tu base de datos ILP",
            "",
            "Archivos ILP (*.ilp)",
        )

        # Usuario canceló.
        if not source_name:
            if not DB_PATH.exists():
                init_db()

            mark_db_setup_prompt_done()
            dialog.accept()
            return

        # Archivo inválido.
        if not validate_database_file(source_name):
            dialog.accept()

            if not DB_PATH.exists():
                init_db()

            mark_db_setup_prompt_done()
            return

        try:
            # Asegurar directorio de destino.
            get_database_path().mkdir(
                parents=True,
                exist_ok=True,
            )

            # Eliminar la base actual únicamente después
            # de comprobar que la nueva es válida.
            if DB_PATH.exists():
                DB_PATH.unlink()

            shutil.copy2(
                source_name,
                DB_PATH,
            )

            # Permite aplicar cualquier inicialización
            # o migración necesaria.
            init_db()

            mark_db_setup_prompt_done()
            dialog.accept()

        except (OSError, sqlite3.Error):
            # No dejamos la aplicación sin una base válida.
            if not DB_PATH.exists():
                init_db()

            mark_db_setup_prompt_done()
            dialog.accept()

    # ------------------------------------------------------
    # Crear base nueva
    # ------------------------------------------------------

    def create_new_db() -> None:
        init_db()
        mark_db_setup_prompt_done()
        dialog.accept()

    # ------------------------------------------------------
    # Conexiones
    # ------------------------------------------------------

    btn_import.clicked.connect(import_existing_db)
    btn_new.clicked.connect(create_new_db)

    layout.addWidget(btn_import)
    layout.addWidget(btn_new)

    dialog.exec()


# ==========================================================
# TEMA
# ==========================================================

def apply_theme(
    app: QApplication,
    theme: str,
) -> bool:
    """
    Carga y aplica el QSS completo del tema.

    El cargador de core.theme combina:

        ui/styles/dark.qss
        ui/styles/light.qss
        ui/styles/components/*.qss
    """
    if theme not in VALID_THEMES:
        theme = DEFAULT_THEME

    qss = load_theme_qss(theme)

    if not qss:
        return False

    app.setStyleSheet(qss)

    return True


# ==========================================================
# APLICACIÓN
# ==========================================================

def main() -> None:
    """
    Inicializa y ejecuta la aplicación.
    """

    # ------------------------------------------------------
    # QApplication
    # ------------------------------------------------------

    app = QApplication(sys.argv)

    app.setApplicationName("ILP")
    app.setApplicationDisplayName("ILP")

    # ------------------------------------------------------
    # Icono de aplicación
    # ------------------------------------------------------

    app_icon_path = get_ui_assets_path(
        "app_icon.svg"
    )

    if app_icon_path.is_file():
        app.setWindowIcon(
            QIcon(str(app_icon_path))
        )

    # ------------------------------------------------------
    # Tema inicial
    # ------------------------------------------------------
    #
    # El tema se aplica antes de crear cualquier ventana.
    # Esto permite que SplashScreen, Wizard, diálogos y
    # MainWindow nazcan con la misma identidad visual.
    #
    theme = get_saved_theme()

    apply_theme(
        app,
        theme,
    )

    # ------------------------------------------------------
    # Splash Screen
    # ------------------------------------------------------

    splash = SplashScreen()
    splash.show()

    window: MainWindow | None = None

    # ------------------------------------------------------
    # Carga principal
    # ------------------------------------------------------

    def load_main_window() -> None:
        nonlocal window

        # ----------------------------------------------
        # Asistente inicial
        # ----------------------------------------------

        if not get_config_path().is_file():
            wizard = SetupWizardDialog()

            if wizard.exec() != QDialog.Accepted:
                splash.close()
                app.quit()
                return

            # El wizard puede haber creado/modificado
            # config.json y seleccionado un tema.
            #
            # Volvemos a aplicar el tema después del wizard.
            selected_theme = get_saved_theme()

            apply_theme(
                app,
                selected_theme,
            )

        # ----------------------------------------------
        # Configuración inicial de base de datos
        # ----------------------------------------------

        prompt_initial_db_setup()

        # Garantizar que la base de datos esté inicializada.
        init_db()

        # ----------------------------------------------
        # Ventana principal
        # ----------------------------------------------

        window = MainWindow()
        window.showMaximized()

        # El splash deja paso a MainWindow.
        splash.finish(window)

    # ------------------------------------------------------
    # Carga diferida
    # ------------------------------------------------------
    #
    # El pequeño retraso permite mostrar correctamente
    # el SplashScreen antes de inicializar el resto.
    #

    QTimer.singleShot(
        1200,
        load_main_window,
    )

    # ------------------------------------------------------
    # Event loop
    # ------------------------------------------------------

    sys.exit(app.exec())


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()