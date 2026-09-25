# core/undo_redo.py
# Sistema de Undo/Redo usando Command Pattern para ILP
from abc import ABC, abstractmethod
from typing import List, Optional
import logging
import json
from database.connection import get_connection

logger = logging.getLogger(__name__)

class Command(ABC):
    """Clase base abstracta para el patrón Command."""
    
    @abstractmethod
    def execute(self) -> bool:
        """Ejecuta la acción."""
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        """Deshace la acción."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Retorna una descripción de la acción para mostrar en el historial."""
        pass

class AuditLogger:
    @staticmethod
    def log_change(tabla: str, registro_id: int, accion: str, 
                   valor_anterior: str = None, valor_nuevo: str = None,
                   campo: str = None, usuario: str = "Sistema", metadata: dict = None):
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None
            cursor.execute("""
                INSERT INTO audit_trail 
                (tabla, registro_id, accion, valor_anterior, valor_nuevo, campo, usuario, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tabla, registro_id, accion, valor_anterior, valor_nuevo, campo, usuario, metadata_json))
            conn.commit()
            logger.info(f"Cambio auditado: {accion} en {tabla} ID {registro_id}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar cambio en audit trail: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_recent_changes(limit: int = 50) -> List[dict]:
        """Obtiene los cambios más recientes del historial."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, tabla, registro_id, accion, valor_anterior, valor_nuevo, 
                       campo, usuario, fecha, metadata
                FROM audit_trail
                ORDER BY fecha DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error al obtener historial de cambios: {e}")
            return []

class UndoRedoManager:
    """Gestor central del sistema de Undo/Redo."""
    
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_history = 100  # Límite de acciones en historial
    
    def execute_command(self, command: Command) -> bool:
        """Ejecuta un comando y lo agrega al stack de undo."""
        try:
            if command.execute():
                self.undo_stack.append(command)
                self.redo_stack.clear()  # Limpiar redo stack cuando se ejecuta nueva acción
                
                # Limitar tamaño del historial
                if len(self.undo_stack) > self.max_history:
                    self.undo_stack.pop(0)
                
                logger.info(f"Comando ejecutado: {command.get_description()}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error al ejecutar comando: {e}")
            return False
    
    def undo(self) -> Optional[str]:
        """Deshace la última acción."""
        if not self.undo_stack:
            return None
        
        command = self.undo_stack.pop()
        try:
            if command.undo():
                self.redo_stack.append(command)
                description = command.get_description()
                logger.info(f"Acción deshecha: {description}")
                return description
            return None
        except Exception as e:
            logger.error(f"Error al deshacer acción: {e}")
            # Reinsertar en undo stack si falla
            self.undo_stack.append(command)
            return None
    
    def redo(self) -> Optional[str]:
        """Rehace la última acción deshecha."""
        if not self.redo_stack:
            return None
        
        command = self.redo_stack.pop()
        try:
            if command.execute():
                self.undo_stack.append(command)
                description = command.get_description()
                logger.info(f"Acción rehecha: {description}")
                return description
            return None
        except Exception as e:
            logger.error(f"Error al rehacer acción: {e}")
            # Reinsertar en redo stack si falla
            self.redo_stack.append(command)
            return None
    
    def can_undo(self) -> bool:
        """Verifica si hay acciones para deshacer."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Verifica si hay acciones para rehacer."""
        return len(self.redo_stack) > 0
    
    def get_undo_description(self) -> str:
        """Obtiene descripción de la próxima acción de undo."""
        if self.undo_stack:
            return self.undo_stack[-1].get_description()
        return ""
    
    def get_redo_description(self) -> str:
        """Obtiene descripción de la próxima acción de redo."""
        if self.redo_stack:
            return self.redo_stack[-1].get_description()
        return ""
    
    def clear_history(self):
        """Limpia todo el historial de undo/redo."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        logger.info("Historial de undo/redo limpiado")

# Instancia global del gestor
undo_redo_manager = UndoRedoManager()
