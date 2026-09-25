# ui/splash_screen.py
from PySide6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QProgressBar
from PySide6.QtCore import Qt, QTimer

class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        self.setFixedSize(450, 220)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Diseño interno limpio sin iconos
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Título principal de la aplicación
        self.title_label = QLabel("Inventario de Logistica Profesional")
        self.title_label.setObjectName("SplashTitle")
        
        # Texto de estado
        self.loading_label = QLabel("Cargando componentes & inicializando base de datos...")
        self.loading_label.setObjectName("SplashLoading")
        
        # Barra de progreso moderna y delgada
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("SplashProgress")
        
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.loading_label, alignment=Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.progress_bar)
        
        # Estilo general de la ventana flotante
        self.setObjectName("SplashScreen")

        # Simular llenado progresivo de la barra durante el arranque
        self.counter = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(15) # Actualiza cada 15ms para una fluidez de 60fps

    def update_progress(self):
        self.counter += 2
        if self.counter <= 100:
            self.progress_bar.setValue(self.counter)
        else:
            self.timer.stop()
    
    def closeEvent(self, event):
        """Detener el timer al cerrar el splash screen."""
        self.timer.stop()
        super().closeEvent(event)