# backup_manager.py
import os
import json
import threading
import time
from datetime import datetime
from typing import List, Dict
from csv_exporter import AttendanceCSVExporter

class BackupManager:
    """Maneja respaldos automáticos y recuperación de datos"""
    
    def __init__(self, backup_dir="backups", auto_backup_interval=300):  # 5 minutos
        self.backup_dir = backup_dir
        self.auto_backup_interval = auto_backup_interval
        self.backup_thread = None
        self.running = False
        self.records = []
        self.lock = threading.Lock()
        
        # Crear directorio de respaldos
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def start_auto_backup(self):
        """Inicia el respaldo automático en segundo plano"""
        if self.backup_thread and self.backup_thread.is_alive():
            return
            
        self.running = True
        self.backup_thread = threading.Thread(target=self._auto_backup_worker)
        self.backup_thread.daemon = True
        self.backup_thread.start()
    
    def stop_auto_backup(self):
        """Detiene el respaldo automático"""
        self.running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=2)
    
    def _auto_backup_worker(self):
        """Worker que ejecuta respaldos periódicos"""
        while self.running:
            try:
                self._create_backup()
                time.sleep(self.auto_backup_interval)
            except Exception as e:
                print(f"Error en respaldo automático: {e}")
                time.sleep(60)  # Reintentar en 1 minuto si hay error
    
    def add_record(self, record: Dict):
        """Agrega un registro al respaldo"""
        with self.lock:
            self.records.append(record)
    
    def add_records(self, records: List[Dict]):
        """Agrega múltiples registros al respaldo"""
        with self.lock:
            self.records.extend(records)
    
    def get_records(self) -> List[Dict]:
        """Obtiene todos los registros"""
        with self.lock:
            return self.records.copy()
    
    def clear_records(self):
        """Limpia todos los registros"""
        with self.lock:
            self.records.clear()
    
    def _create_backup(self):
        """Crea un respaldo de los registros actuales"""
        if not self.records:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"backup_{timestamp}.json")
        
        with self.lock:
            backup_data = {
                "timestamp": timestamp,
                "records_count": len(self.records),
                "records": self.records.copy()
            }
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            print(f"Respaldo creado: {backup_file}")
        except Exception as e:
            print(f"Error creando respaldo: {e}")
    
    def create_emergency_backup(self):
        """Crea un respaldo de emergencia inmediato"""
        if not self.records:
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        emergency_file = os.path.join(self.backup_dir, f"emergency_backup_{timestamp}.json")
        
        with self.lock:
            backup_data = {
                "timestamp": timestamp,
                "type": "emergency",
                "records_count": len(self.records),
                "records": self.records.copy()
            }
        
        try:
            with open(emergency_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            return emergency_file
        except Exception as e:
            print(f"Error creando respaldo de emergencia: {e}")
            return None
    
    def create_csv_backup(self):
        """Crea un respaldo en formato CSV"""
        if not self.records:
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = os.path.join(self.backup_dir, f"backup_{timestamp}.csv")
        
        with self.lock:
            records = self.records.copy()
        
        if AttendanceCSVExporter.export_to_csv(records, csv_file):
            return csv_file
        return None
    
    def load_latest_backup(self) -> List[Dict]:
        """Carga el respaldo más reciente"""
        backup_files = [f for f in os.listdir(self.backup_dir) if f.startswith("backup_") and f.endswith(".json")]
        
        if not backup_files:
            return []
        
        # Ordenar por fecha (más reciente primero)
        backup_files.sort(reverse=True)
        latest_backup = os.path.join(self.backup_dir, backup_files[0])
        
        try:
            with open(latest_backup, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
                return backup_data.get("records", [])
        except Exception as e:
            print(f"Error cargando respaldo: {e}")
            return []
    
    def get_backup_stats(self) -> Dict:
        """Obtiene estadísticas de los respaldos"""
        backup_files = [f for f in os.listdir(self.backup_dir) if f.endswith(".json")]
        
        return {
            "total_backups": len(backup_files),
            "records_in_memory": len(self.records),
            "auto_backup_running": self.running,
            "backup_directory": self.backup_dir
        }
