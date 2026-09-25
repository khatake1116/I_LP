# core/constants.py
from enum import Enum


class PurchaseStatus(str, Enum):
    DRAFT = "Borrador"
    SENT = "Enviada"
    PARTIAL = "Parcial"
    COMPLETED = "Completada"
    CANCELLED = "Cancelada"
    REFUNDED = "Reembolsada"
    DEFECT_RETURNED = "Devuelta por Defecto"

    @classmethod
    def active_values(cls):
        return [
            cls.DRAFT.value,
            cls.SENT.value,
            cls.PARTIAL.value,
        ]

    @classmethod
    def completed_values(cls):
        return [
            cls.COMPLETED.value,
            cls.CANCELLED.value,
            cls.REFUNDED.value,
            cls.DEFECT_RETURNED.value,
        ]


class ShipmentStatus(str, Enum):
    IN_TRANSIT = "En tránsito"
    DELIVERED = "Entregado"
    RETURNED = "Devuelto"
    CANCELLED = "Cancelado"

    @classmethod
    def pending_values(cls):
        return [
            cls.IN_TRANSIT.value,
        ]

    @classmethod
    def completed_values(cls):
        return [
            cls.DELIVERED.value,
            cls.RETURNED.value,
            cls.CANCELLED.value,
        ]


class InventoryMovementType(str, Enum):
    MANUAL_ENTRY = "Entrada manual"
    MANUAL_EXIT = "Salida manual"
    TRANSFER_RECEIVED = "Transferencia recibida"
    TRANSFER_DELIVERED = "Transferencia entregada"
    ADJUSTMENT_POSITIVE = "Ajuste positivo"
    ADJUSTMENT_NEGATIVE = "Ajuste negativo"
    PURCHASE_ENTRY = "Entrada por compra"
    PURCHASE_REVERSAL = "Salida por reversión de compra"
    SHIPMENT_EXIT = "Salida por envío"
    SALE_EXIT = "Salida por venta"

    @classmethod
    def stock_impact_values(cls):
        return [
            cls.MANUAL_ENTRY.value,
            cls.TRANSFER_RECEIVED.value,
            cls.ADJUSTMENT_POSITIVE.value,
            cls.MANUAL_EXIT.value,
            cls.TRANSFER_DELIVERED.value,
            cls.ADJUSTMENT_NEGATIVE.value,
        ]


class PaymentMethod(str, Enum):
    CASH = "Efectivo"
    TRANSFER = "Transferencia"
    CARD = "Tarjeta"
    MIXED = "Mixto"
