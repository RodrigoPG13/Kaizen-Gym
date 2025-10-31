# csv_exporter.py
import csv
from datetime import datetime
from typing import List, Dict

class AttendanceCSVExporter:
    """Clase para manejar la exportación de registros de asistencia a CSV"""
    
    @staticmethod
    def export_to_csv(records: List[Dict], file_path: str) -> bool:
        """
        Exporta una lista de registros de asistencia a un archivo CSV
        
        Args:
            records: Lista de diccionarios con los registros
            file_path: Ruta del archivo donde guardar
            
        Returns:
            bool: True si fue exitoso, False si hubo error
        """
        try:
            if not records:
                return False
                
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'user_id', 'status', 'reason']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Escribir encabezados
                writer.writeheader()
                
                # Escribir registros
                for record in records:
                    writer.writerow({
                        'timestamp': record.get('timestamp', ''),
                        'user_id': record.get('user_id', ''),
                        'status': record.get('status', 'processing'),
                        'reason': record.get('reason', '')
                    })
            
            return True
            
        except Exception as e:
            print(f"Error exportando CSV: {e}")
            return False
    
    @staticmethod
    def generate_filename() -> str:
        """Genera un nombre de archivo único basado en la fecha y hora actual"""
        return f"attendance_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    @staticmethod
    def validate_records(records: List[Dict]) -> List[Dict]:
        """Valida y limpia los registros antes de exportar"""
        validated_records = []
        
        for record in records:
            if isinstance(record, dict) and 'timestamp' in record and 'user_id' in record:
                validated_records.append({
                    'timestamp': str(record.get('timestamp', '')),
                    'user_id': str(record.get('user_id', '')),
                    'status': str(record.get('status', 'processing')),
                    'reason': str(record.get('reason', ''))
                })
        
        return validated_records
