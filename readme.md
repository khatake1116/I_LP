# Inventario y Logística Profesional

Aplicación de escritorio para la gestión de inventario, compras, ventas, envíos y control operativo de stock. Está construida en Python con PySide6 y SQLite, y fue revisada para ajustar la lógica real del negocio: separar claramente A1, tránsito e inventario disponible.

---

## ✅ Auditoría del flujo real del negocio

La lógica correcta del negocio quedó definida de la siguiente manera:

- A1: stock físico en almacén.
- En tránsito: producto ya retirado del almacén o pendiente de entrega, pero aún no operable como inventario real.
- Inventario: stock realmente disponible para vender o mover.
- Venta: descuenta del inventario operativo disponible.
- Transferencia y salida comercial: también deben afectar el inventario disponible y no el stock bruto de A1.

### Regla de negocio aplicada

El sistema ya trabaja con estas reglas:

- El total recibido en compras alimenta la existencia en A1.
- Los envíos pendientes no deben sumarse como inventario disponible.
- Los envíos completados forman parte del ciclo logístico, pero no deben duplicar la existencia.
- La venta solo puede realizarse dentro del rango disponible real.

### Fórmulas de control

- Stock A1 = compras recibidas - envíos creados
- Inventario operativo = entradas logísticas + entregas completadas - salidas de ventas/traspasos
- Validación de venta = cantidad debe estar entre 1 y stock disponible real

Esto evita el error clásico de mezclar A1, tránsito e inventario como si fueran el mismo valor.

---

## 🚀 Funcionalidades principales

- Gestión de artículos, categorías y compras.
- Registro de entradas y compras recibidas.
- Control de envíos pendientes y completados.
- Cálculo de stock por A1, tránsito e inventario disponible.
- Registro de ventas con validación de stock real.
- Dashboard y vistas operativas para monitoreo del inventario.
- Auditoría de movimientos y trazabilidad.
- Interfaz desktop con PySide6.

---

## 📁 Estructura del proyecto

```text
Inventario_Logistica_Profesional/
│
├── main.py                          # Punto de entrada de la aplicación
├── readme.md                       # Documentación principal del proyecto
├── requirements.txt                # Dependencias del proyecto
├── config.json                     # Configuración de la app
├── inventario.ilp                  # Base de datos SQLite local
├── seed_database.py                # Script para sembrar datos iniciales
├── build.py                        # Script de compilación
├── build_simple.py                 # Versión simplificada de build
├── InventarioDuniel.spec           # Especificación de empaquetado
├── estructura.txt                  # Resumen estructural del proyecto
├── memoria.md                      # Registro de memoria del proyecto
├── reporte_mejoras.md              # Reporte de mejoras propuestas
├── reporte_revision_proyecto.md    # Reporte de revisión del proyecto
├── backups/                        # Copias de seguridad de la base de datos
│   └── ...
│
├── core/                           # Lógica central del negocio
│   ├── alerts.py                   # Alertas y recordatorios
│   ├── constants.py                # Enumeraciones y estados del dominio
│   ├── formatting.py               # Utilidades para formateo
│   ├── paths.py                    # Rutas del sistema y recursos
│   └── undo_redo.py                # Auditoría y reversión de cambios
│
├── database/                       # Capa de datos y acceso a SQLite
│   ├── categories.py               # Gestión de categorías
│   ├── connection.py               # Conexión a la base de datos
│   └── models.py                   # Modelos y consultas SQL del inventario
│
├── ui/                             # Capa visual de la aplicación
│   ├── main_window.py              # Ventana principal
│   ├── splash_screen.py            # Pantalla inicial
│   ├── styles.qss                  # Tema visual principal
│   ├── styles_light.qss            # Tema claro
│   ├── assets/
│   │   └── icons/
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── add_sale_dialog.py      # Venta con validación de stock disponible
│   │   ├── category_dialog.py      # Gestión de categorías
│   │   └── setup_wizard.py         # Asistente inicial
│   ├── views/
│   │   ├── adress_view.py          # Vista de direcciones/clientes
│   │   ├── articles_view.py        # Gestión de artículos
│   │   ├── base_view.py            # Base para las vistas
│   │   ├── dashboard_view.py       # Dashboard general
│   │   ├── inventory_view.py       # Vista de inventario y stock
│   │   ├── inventory_movements_view.py
│   │   ├── notifications_view.py   # Notificaciones y alertas
│   │   ├── pos_view.py             # Punto de venta
│   │   ├── purchases_view.py       # Compras
│   │   ├── sales_view.py           # Ventas
│   │   ├── settings_view.py        # Configuración
│   │   ├── shipments_view.py       # Envios/logística
│   │   └── ...
│   └── widgets/
│       ├── __init__.py
│       └── refresh_button.py
│
├── build/                          # Artefactos de compilación
│   ├── InventarioDuniel/
│   └── InventarioLogisticaPro/
│
└── requirements.txt
```

---

## 🧩 Módulos clave

### database/models.py
Centraliza la lógica del inventario y los movimientos. Aquí se calcula el estado real del stock y se validan las operaciones de venta y envío.

### core/constants.py
Define estados de compra, envíos y tipos de movimiento de inventario.

### ui/views/inventory_view.py
Muestra la vista de inventario con los valores operativos y la diferencia entre A1, tránsito e inventario disponible.

### ui/dialogs/add_sale_dialog.py
Controla la tarjeta de venta y bloquea cantidades que excedan el stock real disponible.

### ui/views/shipments_view.py
Administra los envíos pendientes y completados, que son fundamentales para el cálculo de tránsito.

---

## 🔎 Flujo funcional validado

1. El usuario registra una compra.
2. El producto queda recibido en almacén.
3. El sistema lo considera dentro de A1.
4. Si se genera un envío pendiente, ese producto pasa a tránsito.
5. Cuando el envío se completa, el flujo logístico queda cerrado.
6. La venta o movimiento de salida descuenta solamente del stock operativo disponible.
7. El sistema evita vender más unidades de las que realmente existen.

---

## ⚙️ Requisitos

- Python 3.10+
- PySide6
- SQLite

### Instalación

```bash
pip install -r requirements.txt
python main.py
```

---

## 📝 Nota de negocio

Este proyecto fue revisado con el criterio del flujo real del negocio: A1 no es inventario disponible, tránsito no es inventario disponible, y la venta debe limitarse al inventario operable. Esta corrección es la base para mantener una contabilidad coherente y evitar pérdidas por doble conteo o stock artificial.

---

## 🎯 Estado actual

El proyecto está funcionando con la lógica recomendada para la operación real del negocio y con validación de stock aplicada en la venta y en la vista de inventario.
