# ui/views/base_view.py
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QObject, QTimer


class RefreshNotifier(QObject):
    """Canal central para avisar a todas las vistas relacionadas que deben recargarse."""
    refresh_requested = Signal()


class BaseRefreshView(QWidget):
    """Clase base para vistas con funcionalidad de actualización automática."""

    def __init__(self):
        super().__init__()
        self._refresh_notifier = None

    @staticmethod
    def _refreshable_classes():
        from ui.views.dashboard_view import DashboardView
        from ui.views.inventory_view import InventoryView
        from ui.views.inventory_movements_view import InventoryMovementsView
        from ui.views.shipments_view import ShipmentsView
        from ui.views.purchases_view import PurchasesView
        from ui.views.articles_view import ArticlesView
        return (InventoryView, DashboardView, InventoryMovementsView, ShipmentsView, PurchasesView, ArticlesView)

    @property
    def refresh_notifier(self):
        if self._refresh_notifier is None:
            window = self.window()
            if window is None:
                return None
            if not hasattr(window, '_global_refresh_notifier'):
                window._global_refresh_notifier = RefreshNotifier()
            self._refresh_notifier = window._global_refresh_notifier
            self._bind_refresh_signal()
            self._bind_all_related_views_to_notifier(self._refresh_notifier)
        return self._refresh_notifier

    def _bind_all_related_views_to_notifier(self, notifier):
        """Conecta todas las vistas refrescables del mismo window al mismo signal para no depender de una sola vista."""
        if notifier is None:
            return
        window = self.window()
        if window is None:
            return

        for cls in self._refreshable_classes():
            for view in window.findChildren(cls):
                if view is self or not isinstance(view, BaseRefreshView):
                    continue
                view._refresh_notifier = notifier
                view._bind_refresh_signal()

    def _bind_refresh_signal(self):
        notifier = self._refresh_notifier
        if notifier is None:
            return
        try:
            notifier.refresh_requested.disconnect(self.refresh_related_views)
        except (TypeError, RuntimeError):
            pass
        try:
            notifier.refresh_requested.connect(self.refresh_related_views)
        except RuntimeError:
            pass

    def notify_refresh(self):
        window = self.window()
        if window is not None and hasattr(window, 'refresh_all_views'):
            QTimer.singleShot(0, window.refresh_all_views)
            if QApplication.instance() is not None:
                QApplication.processEvents()
            return
        if self.refresh_notifier is not None:
            QTimer.singleShot(0, lambda: self.refresh_notifier.refresh_requested.emit())
            if QApplication.instance() is not None:
                QApplication.processEvents()

    def refresh_related_views(self):
        """Recarga todas las vistas conectadas al inventario para reflejar cambios en tiempo real."""
        window = self.window()
        if window is None:
            return

        if hasattr(window, 'refresh_all_views'):
            window.refresh_all_views()
            return

        for cls in self._refreshable_classes():
            for view in window.findChildren(cls):
                if hasattr(view, 'load_data'):
                    view.load_data()

    def configure_table_sorting(self, table):
        """Activa el ordenamiento y muestra un indicador visual claro de dirección."""
        header = table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        table.setSortingEnabled(True)

        def actualizar_indicador(logical_index, order):
            for column in range(table.columnCount()):
                item = table.horizontalHeaderItem(column)
                if item is None:
                    continue
                texto = item.text()
                texto_limpio = texto.replace("▲ ", "").replace("▼ ", "")
                if column == logical_index:
                    flecha = "▲ " if order == Qt.AscendingOrder else "▼ "
                    item.setText(f"{flecha}{texto_limpio}")
                else:
                    item.setText(texto_limpio)

        header.sortIndicatorChanged.connect(actualizar_indicador)
        if table.columnCount() > 0:
            header.setSortIndicator(0, Qt.AscendingOrder)
            actualizar_indicador(0, Qt.AscendingOrder)
        
