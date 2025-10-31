# zk_listener_thread.py
import time
import asyncio
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QObject
from zk import ZK
from gymforce_api import GymforceAPI


class ZKListenerThread(QThread):
    new_log = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    attendance_record = pyqtSignal(dict)  # Para almacenar registros para CSV
    device_connecting = pyqtSignal()  # Nueva señal para estado de conexión en progreso

    def __init__(self, ip="192.168.100.202", port=4370, poll_interval=5):
        super().__init__()
        self.ip = ip
        self.port = port
        self.poll_interval = poll_interval
        self.running = True
        self.connected = False
        self.connecting = False  # Estado de conexión en progreso
        self.conn = None
        self.last_processed_time = None
        self.api = GymforceAPI()  # 🔗 integración API Gymforce
        self.attendance_records = []  # Para almacenar registros para CSV
        
        # NO crear QTimer aquí - se debe crear en el hilo principal

    def run(self):
        """Método principal del thread - usa eventos en tiempo real cuando es posible"""
        while self.running:
            if not self.connected:
                self.connect_device()
                if not self.connected:
                    self.new_log.emit("[WARN] Reintentando conexión en 5s...")
                    time.sleep(5)
                    continue

            try:
                # Intentar usar listener en tiempo real
                if hasattr(self.conn, 'live_capture'):
                    self.new_log.emit("[INFO] Iniciando captura en tiempo real...")
                    self.start_realtime_capture()
                else:
                    # Fallback a polling optimizado
                    self.new_log.emit("[INFO] Usando polling optimizado...")
                    self.start_optimized_polling()
                    
            except Exception as e:
                self.new_log.emit(f"[ERROR] Error en el loop principal: {e}")
                self.disconnect_device()
                time.sleep(3)

    def start_realtime_capture(self):
        """Captura eventos en tiempo real usando live_capture"""
        try:
            # Configurar callback para eventos en tiempo real
            for attendance in self.conn.live_capture():
                if not self.running:
                    break
                    
                if attendance is None:
                    continue
                    
                # Verificar que la conexión sigue activa
                if not self.conn:
                    break
                    
                # Procesar el evento inmediatamente
                self.process_attendance_record(attendance)
                
        except Exception as e:
            self.new_log.emit(f"[ERROR] Error en captura en tiempo real: {e}")
            self.connected = False
            self.connection_status.emit(False)
            # Fallback a polling si falla tiempo real
            if self.running:
                self.start_optimized_polling()

    def start_optimized_polling(self):
        """Polling optimizado que solo busca registros nuevos"""
        try:
            self._initialize_polling_timestamp()
            
            while self.running and self.connected:
                try:
                    self._poll_and_process_records()
                    time.sleep(self.poll_interval)
                    
                except Exception as e:
                    self.new_log.emit(f"[ERROR] Error en polling: {e}")
                    time.sleep(2)
                    
        except Exception as e:
            self.new_log.emit(f"[ERROR] Error fatal en polling: {e}")
    
    def _initialize_polling_timestamp(self):
        """Inicializa el timestamp para el polling"""
        if self.last_processed_time is None:
            # Obtener el registro más reciente como punto de partida
            if self.conn:
                records = self.conn.get_attendance()
                if records:
                    self.last_processed_time = max(r.timestamp for r in records)
                    self.new_log.emit(f"[INFO] Punto de inicio: {self.last_processed_time}")
                else:
                    self.last_processed_time = datetime.now()
            else:
                self.last_processed_time = datetime.now()
    
    def _poll_and_process_records(self):
        """Obtiene y procesa registros nuevos"""
        if not self.conn:
            return
            
        records = self.conn.get_attendance()
        new_records = []
        
        if records:
            for r in records:
                if r.timestamp > self.last_processed_time:
                    new_records.append(r)
            
            # Procesar solo registros nuevos
            for record in sorted(new_records, key=lambda x: x.timestamp):
                self.process_attendance_record(record)
                self.last_processed_time = record.timestamp

    def process_attendance_record(self, record):
        """Procesa un registro de asistencia individual"""
        try:
            socio_id = str(record.user_id).strip()
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            self.new_log.emit(f"[{timestamp}] 📍 Procesando Usuario={socio_id}")
            
            # Almacenar registro para CSV
            record_data = {
                'timestamp': timestamp,
                'user_id': socio_id,
                'status': 'processing'
            }
            self.attendance_records.append(record_data)
            self.attendance_record.emit(record_data)

            # ⚡ Llamada SINCRÓNICA al endpoint (para prueba)
            try:
                result = self.api.validar_acceso(socio_id)
                
                if result.get("access") == "allow":
                    msg = f"[{timestamp}] ✅ Usuario {socio_id} - Acceso PERMITIDO"
                    status = "allowed"
                    # Registrar visita exitosa
                    self.api.registrar_visita(socio_id, timestamp)
                else:
                    reason = result.get("respuesta", "Sin motivo especificado")
                    msg = f"[{timestamp}] ❌ Usuario {socio_id} - Acceso DENEGADO: {reason}"
                    status = "denied"

                # Actualizar registro para CSV
                for rec in self.attendance_records:
                    if rec['user_id'] == socio_id and rec['timestamp'] == timestamp:
                        rec['status'] = status
                        rec['reason'] = result.get("respuesta", "")
                        break

                self.new_log.emit(msg)

            except Exception as api_error:
                self.new_log.emit(f"[ERROR] Falló la validación con API: {api_error}")

        except Exception as e:
            self.new_log.emit(f"[ERROR] Error procesando registro: {e}")


    def validate_access_async(self, socio_id: str, timestamp: str):
        """Valida acceso de forma no bloqueante usando callback"""
        def callback(user_id: str, result: dict):
            try:
                if result.get("access") == "allow":
                    msg = f"[{timestamp}] ✅ Usuario {user_id} - Acceso PERMITIDO"
                    status = "allowed"
                    # Registrar visita exitosa
                    self.api.registrar_visita(user_id, timestamp)
                else:
                    reason = result.get("respuesta", "Sin motivo especificado")
                    msg = f"[{timestamp}] ❌ Usuario {user_id} - Acceso DENEGADO: {reason}"
                    status = "denied"
                
                # Actualizar registro para CSV
                for record in self.attendance_records:
                    if record['user_id'] == user_id and record['timestamp'] == timestamp:
                        record['status'] = status
                        record['reason'] = result.get("respuesta", "")
                        break
                
                self.new_log.emit(msg)
                
            except Exception as e:
                self.new_log.emit(f"[ERROR] Error procesando resultado para {user_id}: {e}")
        
        # Llamada asíncrona que no bloquea el hilo principal
        self.api.validar_acceso_async(socio_id, callback)

    def register_visit(self, socio_id: str, timestamp: str):
        """Registra la visita en el sistema (puedes expandir esto)"""
        try:
            # Aquí puedes agregar lógica adicional para registrar la visita
            # Por ejemplo, guardar en base de datos local, enviar a otro API, etc.
            self.new_log.emit(f"[VISIT] Visita registrada para usuario {socio_id}")
        except Exception as e:
            self.new_log.emit(f"[ERROR] Error registrando visita: {e}")

    def connect_device(self):
        self.connecting = True
        self.device_connecting.emit()  # Emitir señal de que está conectando
        
        zk = ZK(self.ip, port=self.port, timeout=5, password=0, force_udp=False)
        try:
            self.conn = zk.connect()
            self.conn.disable_device()
            self.connected = True
            self.connecting = False
            self.connection_status.emit(True)
            self.new_log.emit(f"[OK] Conectado al dispositivo {self.ip}:{self.port}")
            
        except Exception as e:
            self.connected = False
            self.connecting = False
            self.connection_status.emit(False)
            self.new_log.emit(f"[ERROR] No se pudo conectar: {e}")

    def disconnect_device(self):
        if self.conn:
            try:
                self.conn.enable_device()
                self.conn.disconnect()
            except Exception:
                pass
        self.conn = None
        self.connected = False
        self.connection_status.emit(False)
        self.new_log.emit("[INFO] Desconectado del dispositivo")

    def get_attendance_records(self):
        """Devuelve los registros de asistencia para exportar"""
        return self.attendance_records.copy()

    def stop(self):
        self.running = False
        # Cerrar API de forma limpia
        if hasattr(self.api, 'close'):
            self.api.close()
        self.disconnect_device()
        self.quit()
        self.wait()
