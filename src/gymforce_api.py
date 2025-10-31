# gymforce_api.py
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Callable, Optional

class GymforceAPI:
    BASE_URL = "https://kaizengyml.gymforce.mx"
    LOGIN_ENDPOINT = "/api/torniquete/users/login"
    ACCESS_ENDPOINT = "/api/torniquete/socio/acceso"

    EMAIL = "torniquete.kaizen@gymforce.mx"
    PASSWORD = "KaizenInt_2025_RPzM9y72jG5Qw48Lc1NtXb3"

    def __init__(self, max_workers=3):
        self.token = None
        self.token_expiration = 0
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.session = requests.Session()
        # Configurar timeouts por defecto
        self.session.timeout = (5, 10)  # (connect_timeout, read_timeout)

    def login(self):
        """Obtiene el token Bearer."""
        try:
            res = self.session.post(
                f"{self.BASE_URL}{self.LOGIN_ENDPOINT}",
                json={"email": self.EMAIL, "password": self.PASSWORD},
                timeout=5,
            )
            if res.status_code == 200:
                data = res.json()
                with self.lock:
                    self.token = data["token"]
                    self.token_expiration = time.time() + int(data.get("expires_in", 7200))
                print("[GymforceAPI] ✅ Login exitoso.")
                return True
            else:
                print(f"[GymforceAPI] ❌ Error de login: {res.status_code} {res.text}")
        except Exception as e:
            print(f"[GymforceAPI] ⚠️ Excepción en login: {e}")
        return False

    def ensure_token(self):
        with self.lock:
            token_valid = self.token and time.time() < self.token_expiration
        if not token_valid:
            return self.login()
        return True


    def validar_acceso(self, socio_id: str, sucursal_id: int = 1) -> Dict:
        """Consulta si el socio tiene acceso permitido."""
        if not self.ensure_token():
            return {"status": "ERROR", "access": "deny", "respuesta": "Sin token válido"}

        try:
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
            payload = {"socio_id": socio_id, "sucursal_id": sucursal_id}

            res = self.session.post(
                f"{self.BASE_URL}{self.ACCESS_ENDPOINT}", 
                headers=headers, 
                json=payload, 
                timeout=5
            )
            
            if res.status_code == 200:
                data = res.json()
                return data
            elif res.status_code == 401:
                # Token expirado, reintenta una vez
                print("[GymforceAPI] ⚠️ Token expirado. Renovando...")
                if self.login():
                    return self.validar_acceso(socio_id, sucursal_id)
            else:
                print(f"[GymforceAPI] ❌ Error {res.status_code}: {res.text}")
                return {"status": "ERROR", "access": "deny", "respuesta": f"HTTP {res.status_code}"}
                
        except requests.exceptions.Timeout:
            print(f"[GymforceAPI] ⏰ Timeout validando acceso para {socio_id}")
            return {"status": "ERROR", "access": "deny", "respuesta": "Timeout"}
        except Exception as e:
            print(f"[GymforceAPI] ⚠️ Error de red: {e}")
            return {"status": "ERROR", "access": "deny", "respuesta": str(e)}

    def validar_acceso_async(self, socio_id: str, callback: Callable[[str, Dict], None], 
                           sucursal_id: int = 1):
        """Valida acceso de forma asíncrona usando ThreadPoolExecutor."""
        def _validate():
            try:
                result = self.validar_acceso(socio_id, sucursal_id)
                callback(socio_id, result)
            except Exception as e:
                callback(socio_id, {"status": "ERROR", "access": "deny", "respuesta": str(e)})
        
        self.executor.submit(_validate)

    def registrar_visita(self, socio_id: str, timestamp: str, sucursal_id: int = 1) -> Dict:
        """Registra una visita en el sistema (si existe endpoint)."""
        # Este método puedes implementarlo cuando tengas el endpoint correspondiente
        # Por ahora solo simula el registro
        try:
            print(f"[GymforceAPI] 📝 Registrando visita: Socio {socio_id} en {timestamp}")
            return {"status": "OK", "message": "Visita registrada"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def close(self):
        """Cierra el executor y la sesión."""
        self.executor.shutdown(wait=True)
        self.session.close()
