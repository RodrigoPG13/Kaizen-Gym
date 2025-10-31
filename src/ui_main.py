# ui_main.py
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit, QHBoxLayout, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from zk_listener import ZKListenerThread
from csv_exporter import AttendanceCSVExporter
from backup_manager import BackupManager


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZKTeco SpeedFace V4L - Monitor")
        self.resize(700, 500)
        
        # Inicializar sistema de respaldo
        self.backup_manager = BackupManager()
        self.backup_manager.start_auto_backup()
        
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #E0E0E0;
                font-family: "Segoe UI";
            }
            QPushButton {
                background-color: #1E88E5;
                color: white;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #757575;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #C8E6C9;
                border: 1px solid #333;
                font-family: "Consolas";
                font-size: 12px;
            }
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFF;
                border: 1px solid #333;
                padding: 4px;
            }
            QLabel {
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout()

        # ---- Connection fields ----
        conn_layout = QHBoxLayout()
        self.ip_input = QLineEdit("192.168.100.202")
        self.port_input = QLineEdit("4370")
        self.ip_input.setFixedWidth(150)
        self.port_input.setFixedWidth(80)
        conn_layout.addWidget(QLabel("IP:"))
        conn_layout.addWidget(self.ip_input)
        conn_layout.addWidget(QLabel("Puerto:"))
        conn_layout.addWidget(self.port_input)

        self.connect_btn = QPushButton("Conectar")
        self.disconnect_btn = QPushButton("Desconectar")
        self.export_btn = QPushButton("Exportar CSV")
        
        # Estado inicial de botones
        self.disconnect_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.disconnect_btn)
        conn_layout.addWidget(self.export_btn)

        layout.addLayout(conn_layout)

        # ---- Status label ----
        self.status_label = QLabel("Estado: Desconectado")
        layout.addWidget(self.status_label)

        # ---- Log window ----
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.setLayout(layout)

        # ---- Thread setup ----
        self.listener_thread = None
        self.attendance_records = []  # Para almacenar registros para CSV

        # ---- Button actions ----
        self.connect_btn.clicked.connect(self.start_listener)
        self.disconnect_btn.clicked.connect(self.stop_listener)
        self.export_btn.clicked.connect(self.export_to_csv)
        
        # Configurar cierre seguro
        self.setup_close_handler()

    def append_log(self, text: str):
        self.log_box.append(text)
        cursor = self.log_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_box.setTextCursor(cursor)

    def setup_close_handler(self):
        """Configura el manejo del cierre de la aplicación"""
        # Override del evento de cierre
        import signal
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Maneja señales del sistema para cierre limpio"""
        self.closeEvent(None)

    def closeEvent(self, event):
        """Maneja el cierre de la aplicación con guardado automático"""
        try:
            # Preguntar si desea guardar antes de cerrar
            if self.attendance_records or (self.listener_thread and self.listener_thread.get_attendance_records()):
                reply = QMessageBox.question(
                    self, 
                    'Guardar datos', 
                    '¿Desea guardar los registros antes de cerrar?\n\nSe recomienda guardar para no perder los datos.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Cancel:
                    if event:
                        event.ignore()
                    return
                
                elif reply == QMessageBox.StandardButton.Yes:
                    self.save_before_close()
            
            # Crear respaldo de emergencia
            self.create_emergency_backup()
            
            # Detener listener
            if self.listener_thread:
                self.listener_thread.stop()
                self.listener_thread = None
            
            # Detener respaldo automático
            self.backup_manager.stop_auto_backup()
            
            self.append_log("[INFO] Aplicación cerrada de forma segura")
            
            if event:
                event.accept()
            else:
                QApplication.quit()
                
        except Exception as e:
            print(f"Error al cerrar: {e}")
            if event:
                event.accept()
            else:
                QApplication.quit()

    def save_before_close(self):
        """Guarda los registros antes de cerrar"""
        try:
            # Obtener todos los registros
            all_records = self.attendance_records.copy()
            if self.listener_thread:
                thread_records = self.listener_thread.get_attendance_records()
                all_records.extend(thread_records)
            
            if all_records:
                # Agregar al backup manager
                self.backup_manager.add_records(all_records)
                
                # Crear archivo CSV de cierre
                suggested_filename = f"closing_backup_{AttendanceCSVExporter.generate_filename()}"
                file_path, _ = QFileDialog.getSaveFileName(
                    self, 
                    "Guardar registros antes de cerrar", 
                    suggested_filename,
                    "CSV Files (*.csv)"
                )
                
                if file_path:
                    validated_records = AttendanceCSVExporter.validate_records(all_records)
                    success = AttendanceCSVExporter.export_to_csv(validated_records, file_path)
                    
                    if success:
                        QMessageBox.information(
                            self, 
                            "Guardado exitoso", 
                            f"Registros guardados en:\n{file_path}"
                        )
                    else:
                        QMessageBox.warning(
                            self, 
                            "Error al guardar", 
                            "No se pudo guardar el archivo CSV"
                        )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Error al guardar antes de cerrar:\n{str(e)}"
            )

    def create_emergency_backup(self):
        """Crea un respaldo de emergencia silencioso"""
        try:
            # Obtener todos los registros
            all_records = self.attendance_records.copy()
            if self.listener_thread:
                thread_records = self.listener_thread.get_attendance_records()
                all_records.extend(thread_records)
            
            if all_records:
                self.backup_manager.add_records(all_records)
                emergency_file = self.backup_manager.create_emergency_backup()
                csv_file = self.backup_manager.create_csv_backup()
                
                if emergency_file or csv_file:
                    self.append_log(f"[BACKUP] Respaldo de emergencia creado")
                    
        except Exception as e:
            print(f"Error en respaldo de emergencia: {e}")

    def update_status(self, connected: bool):
        if connected:
            self.status_label.setText("Estado: ✅ Conectado")
            self.status_label.setStyleSheet("color: #81C784; font-weight: bold;")
            # Actualizar estado de botones cuando se conecta
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Conectado")
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_label.setText("Estado: ❌ Desconectado")
            self.status_label.setStyleSheet("color: #EF5350; font-weight: bold;")
            # Actualizar estado de botones cuando se desconecta
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Conectar")
            self.disconnect_btn.setEnabled(False)

    def on_device_connecting(self):
        """Maneja el estado cuando el dispositivo está conectando"""
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Conectando...")
        self.disconnect_btn.setEnabled(False)

    def start_listener(self):
        ip = self.ip_input.text().strip()
        port = int(self.port_input.text().strip())
        self.listener_thread = ZKListenerThread(ip=ip, port=port)
        
        # Conectar señales
        self.listener_thread.new_log.connect(self.append_log)
        self.listener_thread.connection_status.connect(self.update_status)
        self.listener_thread.attendance_record.connect(self.store_attendance_record)
        self.listener_thread.device_connecting.connect(self.on_device_connecting)  # Nueva señal
        
        self.listener_thread.start()

        self.append_log(f"[INFO] Intentando conectar con {ip}:{port}...")
        # Los botones se actualizarán automáticamente cuando llegue la señal de conexión

    def store_attendance_record(self, record):
        """Almacena los registros de asistencia para exportación"""
        self.attendance_records.append(record)
        # También agregar al backup manager para respaldo automático
        self.backup_manager.add_record(record)

    def stop_listener(self):
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread = None
            self.append_log("[INFO] Listener detenido.")
        # Los botones se actualizarán automáticamente cuando llegue la señal de desconexión
        self.update_status(False)

    def export_to_csv(self):
        """Exporta los registros de asistencia a un archivo CSV"""
        if not self.attendance_records:
            QMessageBox.information(self, "Exportar CSV", "No hay registros para exportar.")
            return
        
        # Obtener registros del hilo si está disponible
        if self.listener_thread:
            thread_records = self.listener_thread.get_attendance_records()
            # Combinar registros
            all_records = self.attendance_records + thread_records
        else:
            all_records = self.attendance_records
        
        if not all_records:
            QMessageBox.information(self, "Exportar CSV", "No hay registros para exportar.")
            return
        
        # Diálogo para guardar archivo
        suggested_filename = AttendanceCSVExporter.generate_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar archivo CSV", 
            suggested_filename,
            "CSV Files (*.csv)"
        )
        
        if file_path:
            # Validar y limpiar registros
            validated_records = AttendanceCSVExporter.validate_records(all_records)
            
            # Exportar usando el exportador
            success = AttendanceCSVExporter.export_to_csv(validated_records, file_path)
            
            if success:
                QMessageBox.information(
                    self, 
                    "Exportar CSV", 
                    f"Archivo guardado exitosamente:\n{file_path}\n\nRegistros exportados: {len(validated_records)}"
                )
            else:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Error al guardar el archivo:\n{file_path}"
                )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
