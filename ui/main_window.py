# ui/main_window.py
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QPushButton, QStackedWidget, QLabel, QFrame,
                               QSystemTrayIcon, QMenu, QComboBox, QTabWidget, QMessageBox,
                               QApplication)
from PySide6.QtCore import Qt, QPropertyAnimation, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap, QRegion
from PySide6.QtSvg import QSvgRenderer
import json
import re
from core.paths import get_config_path

from core.alerts import obtener_alertas_retrasos
from core.paths import get_ui_icons_path, get_ui_assets_path
from ui.views.inventory_view import InventoryView
from ui.views.inventory_movements_view import InventoryMovementsView
from ui.views.dashboard_view import DashboardView
from ui.views.sales_view import SalesView
from ui.views.purchases_view import PurchasesView
from ui.views.shipments_view import ShipmentsView
from ui.views.articles_view import ArticlesView
from ui.views.notifications_view import NotificationsView
from ui.views.settings_view import SettingsView
from ui.views.adress_view import AdressView
from ui.views.base_view import RefreshNotifier
from database.models import print_formula_validation_report

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventario de Logística Profesional")
        self._global_refresh_notifier = RefreshNotifier()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
      
        # --- SIDEBAR LATERAL ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        sidebar_layout.setSpacing(8)

        # Botón de colapso ("Panel")
        self.btn_toggle = QPushButton("  Panel")
        self.btn_toggle.setObjectName("SidebarToggle")
        
        # Cargar icono para el botón de toggle
        try:
            icon_path = get_ui_icons_path("dashboard.svg")
            if icon_path.exists():
                self.btn_toggle.setIcon(QIcon(str(icon_path)))
                self.btn_toggle.setIconSize(QSize(20, 20))
        except Exception:
            pass  # Si falla la carga del icono, continuar sin él
            
        self.btn_toggle.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.btn_toggle)

        sidebar_layout.addSpacing(15)
    
        # Botones del Menú con sus respectivos iconos SVG y rutas limpias
        self.nav_buttons = []
        self.current_theme = self.load_config().get("theme", "dark")
        active_modules = self.load_config().get("modulos_activos", {})
        nav_specs = (
            ("  Ventas / POS", 0, "articles.svg", active_modules.get("ventas", True)),
            ("  Inventario", 1, "inventory.svg", active_modules.get("inventario", True)),
            ("  Compras", 2, "purchases.svg", active_modules.get("compras", True)),
            ("  Logística", 3, "shipments.svg", active_modules.get("logistica", True)),
            ("  Configuración", 4, "settings.svg", True),
        )
        for text, index, icon, is_active in nav_specs:
            button = self.create_nav_btn(text, index, icon)
            button.setVisible(is_active)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()

        main_layout.addWidget(self.sidebar)

        print_formula_validation_report()

        # --- CONTENEDOR PRINCIPAL Y VISTAS ---
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(15, 15, 15, 15)

        self.header = QFrame()
        self.header.setObjectName("TopHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 8)

        self.alerta_label = QLabel("Revisando estado de envíos...")
        self.alerta_label.setObjectName("AlertaLabel")
        self.alerta_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.alerta_label, 1)
        header_layout.addWidget(self.create_profile_widget())
        content_layout.addWidget(self.header)

        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView()
        self.dashboard_view._refresh_notifier = self._global_refresh_notifier
        self.dashboard_view._bind_refresh_signal()

        self.sales_view = SalesView()
        self.sales_view._refresh_notifier = self._global_refresh_notifier
        self.sales_view._bind_refresh_signal()

        sales_tabs = QTabWidget()
        sales_tabs.setObjectName("SalesTabs")
        sales_tabs.addTab(self.dashboard_view, "Dashboard")
        sales_tabs.addTab(self.sales_view, "Ventas")
        self.stack.addWidget(sales_tabs)

        self.inventory_view = InventoryView()
        self.inventory_view._refresh_notifier = self._global_refresh_notifier
        self.inventory_view._bind_refresh_signal()
        self.stack.addWidget(self.inventory_view)
        self.purchases_view = PurchasesView()
        self.purchases_view._refresh_notifier = self._global_refresh_notifier
        self.purchases_view._bind_refresh_signal()
        self.stack.addWidget(self.purchases_view)
        logistics_tabs = QTabWidget()
        logistics_tabs.setObjectName("LogisticsTabs")
        self.pending_shipments_view = ShipmentsView(filter_type="pending")
        self.pending_shipments_view._refresh_notifier = self._global_refresh_notifier
        self.pending_shipments_view._bind_refresh_signal()
        self.completed_shipments_view = ShipmentsView(filter_type="completed")
        self.completed_shipments_view._refresh_notifier = self._global_refresh_notifier
        self.completed_shipments_view._bind_refresh_signal()
        logistics_tabs.addTab(self.pending_shipments_view, "Envíos Pendientes")
        logistics_tabs.addTab(self.completed_shipments_view, "Envíos Completados")
        self.address_view = AdressView()
        self.address_view._refresh_notifier = self._global_refresh_notifier
        self.address_view._bind_refresh_signal()
        self.catalog_view = ArticlesView()
        self.catalog_view._refresh_notifier = self._global_refresh_notifier
        self.catalog_view._bind_refresh_signal()
        logistics_tabs.addTab(self.address_view, "Destinatarios")
        logistics_tabs.addTab(self.catalog_view, "Catálogo")
        self.stack.addWidget(logistics_tabs)
        self.settings_view = SettingsView()
        self.settings_view._refresh_notifier = self._global_refresh_notifier
        self.settings_view._bind_refresh_signal()
        self.settings_view.profile_updated.connect(self.update_profile_header)
        self.stack.addWidget(self.settings_view)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_container, 1)  # Stretch factor 1 para que se expanda

        self.is_collapsed = False
        self.check_alerts()
        
        # Configurar System Tray
        self.setup_system_tray()

    def create_profile_widget(self):
        """Construye el perfil de sucursal y el selector de moneda del encabezado."""
        profile = QWidget()
        layout = QHBoxLayout(profile)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        config = self.load_config()
        company = config.get("empresa") or config.get("company_name") or "Inventario Duniel"
        branch = config.get("sucursal") or config.get("branch") or "Sucursal principal"
        initials = "".join(part[0] for part in company.split()[:2]).upper() or "ID"

        avatar = QLabel(initials)
        avatar.setObjectName("ProfileAvatar")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        logo_path = config.get("logo")
        if logo_path:
            logo = QPixmap(logo_path)
            if not logo.isNull():
                avatar.setPixmap(logo.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                avatar.setText("")
        avatar.setMask(QRegion(0, 0, 40, 40, QRegion.Ellipse))
        layout.addWidget(avatar)

        self.exchange_rate_label = QLabel()
        self.exchange_rate_label.setObjectName("ExchangeRateLabel")
        self.set_exchange_rate(config.get("tasa_cambio", 1.0))
        layout.addWidget(self.exchange_rate_label)

        identity = QVBoxLayout()
        identity.setSpacing(0)
        company_label = QLabel(company)
        company_label.setObjectName("ProfileCompany")
        branch_label = QLabel(branch)
        branch_label.setObjectName("ProfileBranch")
        identity.addWidget(company_label)
        identity.addWidget(branch_label)
        layout.addLayout(identity)

        self.currency_combo = QComboBox()
        self.currency_combo.setObjectName("CurrencyCombo")
        self.currency_combo.addItems(["CUP", "USD"])
        self.currency_combo.setCurrentText(config.get("moneda", "CUP"))
        self.currency_combo.currentTextChanged.connect(self.on_currency_changed)
        layout.addWidget(self.currency_combo)
        self.profile_company_label = company_label
        self.profile_branch_label = branch_label
        self.profile_avatar = avatar
        return profile

    @staticmethod
    def load_config():
        try:
            config_file = get_config_path()
            if config_file.exists():
                with config_file.open("r", encoding="utf-8") as config_data:
                    return json.load(config_data)
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def on_currency_changed(self, currency):
        if hasattr(self.dashboard_view, 'set_currency'):
            self.dashboard_view.set_currency(currency)
        self.refresh_all_views()

    def update_profile_header(self, config):
        company = config.get("empresa", "Inventario Duniel")
        branch = config.get("sucursal", "Sucursal principal")
        self.profile_company_label.setText(company)
        self.profile_branch_label.setText(branch)
        self.currency_combo.setCurrentText(config.get("moneda", "CUP"))
        self.set_exchange_rate(config.get("tasa_cambio", 1.0))
        initials = "".join(part[0] for part in company.split()[:2]).upper() or "ID"
        self.profile_avatar.setText(initials)
        logo_path = config.get("logo")
        if logo_path:
            logo = QPixmap(logo_path)
            if not logo.isNull():
                self.profile_avatar.setPixmap(logo.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                self.profile_avatar.setText("")

    def set_exchange_rate(self, rate):
        try:
            value = float(rate)
        except (TypeError, ValueError):
            value = 1.0
        self.exchange_rate_label.setText(f"{value:,.2f}".replace(",", "'") + " CUP/USD")

    def create_nav_btn(self, text, index, icon_filename):
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setProperty("iconFilename", icon_filename)
        btn.setIcon(self.create_themed_icon(icon_filename))
        btn.setIconSize(QSize(20, 20))
        
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.switch_page(index))
        if index == 0:
            btn.setChecked(True)
        self.nav_buttons.append(btn)
        return btn

    def create_themed_icon(self, icon_filename):
        icon_path = get_ui_icons_path(icon_filename)
        if not icon_path.exists():
            return QIcon()
        try:
            svg = icon_path.read_text(encoding="utf-8")
            color = "#2C3E50" if self.current_theme == "light" else "#CDD6F4"
            svg = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', svg)
            renderer = QSvgRenderer(svg.encode("utf-8"))
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except (OSError, RuntimeError):
            return QIcon(str(icon_path))

    def update_nav_icons(self, theme):
        self.current_theme = theme
        for button in self.nav_buttons:
            icon_filename = button.property("iconFilename")
            button.setIcon(self.create_themed_icon(icon_filename))

    def refresh_all_views(self):
        """Recarga todas las vistas activas del sistema para reflejar cambios en tiempo real."""
        seen = set()

        def visit(widget):
            if widget is None or id(widget) in seen:
                return
            seen.add(id(widget))

            if hasattr(widget, 'load_data'):
                try:
                    widget.load_data()
                except Exception:
                    pass

            if isinstance(widget, QTabWidget):
                for index in range(widget.count()):
                    visit(widget.widget(index))
            elif isinstance(widget, QStackedWidget):
                for index in range(widget.count()):
                    visit(widget.widget(index))

        inventory_movements_widget = getattr(self.inventory_view, 'movements_tab', None)

        for view in [
            self.dashboard_view,
            self.sales_view,
            self.inventory_view,
            inventory_movements_widget,
            self.purchases_view,
            self.pending_shipments_view,
            self.completed_shipments_view,
            self.settings_view,
            self.address_view,
            self.catalog_view,
        ]:
            if view is not None:
                visit(view)

        self.update()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def toggle_sidebar(self):
        current_width = self.sidebar.width()
        target_width = 70 if current_width == 220 else 220
        
        self.anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.anim.setDuration(200)
        self.anim.setStartValue(current_width)
        self.anim.setEndValue(target_width)
        
        self.anim2 = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.anim2.setDuration(200)
        self.anim2.setStartValue(current_width)
        self.anim2.setEndValue(target_width)
        
        self.anim.start()
        self.anim2.start()
        self.is_collapsed = (target_width == 70)

    def check_alerts(self):
        dias_limite = 7
        config_file = get_config_path()
        try:
            if config_file.exists():
                with config_file.open("r", encoding="utf-8") as config_data:
                    config = json.load(config_data)
                dias_limite = config.get("dias_alerta_compras", dias_limite)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

        alertas = obtener_alertas_retrasos(dias_limite=dias_limite)
        if not alertas:
            self.alerta_label.clear()
            self.alerta_label.setVisible(False)
            self.alerta_label.setProperty("alertLevel", "normal")
        else:
            self.alerta_label.setText(f"⚠️ ALERTA: Tienes {len(alertas)} envío(s) estancado(s) por más de {dias_limite} días.")
            self.alerta_label.setVisible(True)
            self.alerta_label.setProperty("alertLevel", "error")
        self.alerta_label.style().unpolish(self.alerta_label)
        self.alerta_label.style().polish(self.alerta_label)

    def setup_system_tray(self):
        """Configura el icono en la bandeja del sistema (System Tray)."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System Tray no disponible en este sistema")
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        
        # Cargar icono para el tray - priorizar .ico para mejor compatibilidad en Windows
        icon_loaded = False
        try:
            # Intentar primero con .ico (mejor para System Tray en Windows)
            icon_path = get_ui_assets_path("app_icon.ico")
            print(f"Ruta del icono .ico: {icon_path}")
            print(f"El archivo .ico existe: {icon_path.exists()}")
            
            if icon_path.exists():
                tray_icon = QIcon(str(icon_path))
                if not tray_icon.isNull():
                    self.tray_icon.setIcon(tray_icon)
                    icon_loaded = True
                    print("Icono .ico cargado exitosamente")
                else:
                    print("El icono .ico es nulo")
            else:
                print("El archivo .ico no existe")
                
                # Fallback a .svg
                icon_path_svg = get_ui_assets_path("app_icon.svg")
                print(f"Ruta del icono .svg: {icon_path_svg}")
                print(f"El archivo .svg existe: {icon_path_svg.exists()}")
                
                if icon_path_svg.exists():
                    tray_icon = QIcon(str(icon_path_svg))
                    if not tray_icon.isNull():
                        self.tray_icon.setIcon(tray_icon)
                        icon_loaded = True
                        print("Icono .svg cargado exitosamente")
                    else:
                        print("El icono .svg es nulo")
        except Exception as e:
            print(f"Error al cargar icono personalizado: {e}")
        
        # Si no se cargó ningún icono, usar icono estándar de Qt
        if not icon_loaded:
            print("Usando icono estándar de Qt como fallback")
            try:
                self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
            except Exception as e:
                print(f"Error al cargar icono estándar: {e}")
                # Último recurso: crear un icono simple
                from PySide6.QtGui import QPixmap
                from PySide6.QtCore import Qt
                pixmap = QPixmap(16, 16)
                pixmap.fill(Qt.blue)
                self.tray_icon.setIcon(QIcon(pixmap))
        
        # Verificar que el icono se haya cargado
        if self.tray_icon.icon().isNull():
            print("ADVERTENCIA: El icono del System Tray es nulo")
        else:
            print("Icono del System Tray cargado correctamente")
        
        # Crear menú contextual del tray
        tray_menu = QMenu()
        
        action_show = tray_menu.addAction("Mostrar")
        action_show.triggered.connect(self.show)

        tray_menu.addSeparator()

        action_quit = tray_menu.addAction("Salir")
        action_quit.triggered.connect(self.force_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Doble clic para mostrar/ocultar
        self.tray_icon.activated.connect(self.tray_activated)
        
        self.tray_icon.show()
    
    def tray_activated(self, reason):
        """Maneja la activación del icono de tray (doble clic)."""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def force_quit(self):
        """Cierra la aplicación completamente sin preguntar."""
        self._force_quit_requested = True
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Intercepta el evento de cierre para mostrar diálogo de confirmación."""
        if getattr(self, '_force_quit_requested', False):
            event.accept()
            return

        reply = QMessageBox.question(
            self, "Confirmar Salida",
            "¿Estás seguro de que deseas salir o prefieres minimizar al concentrador de notificaciones (Bandeja del sistema)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            event.accept()
        else:
            self.hide()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.showMessage(
                    "Inventario de Logística Profesional",
                    "La aplicación sigue ejecutándose en la bandeja del sistema.",
                    QSystemTrayIcon.Information,
                    3000
                )
            event.ignore()