# config.py
"""
Configuraciones centralizadas para el sistema de torniquete
"""

# Configuración del dispositivo ZKTeco
ZK_CONFIG = {
    'default_ip': '192.168.100.202',
    'default_port': 4370,
    'timeout': 5,
    'password': 0,
    'force_udp': False,
    'poll_interval': 5,  # segundos entre polling (solo si no hay tiempo real)
    'heartbeat_interval': 30,  # segundos para verificar conexión
}

# Configuración de la API
API_CONFIG = {
    'base_url': 'https://kaizengyml.gymforce.mx',
    'login_endpoint': '/api/torniquete/users/login',
    'access_endpoint': '/api/torniquete/socio/acceso',
    'email': 'torniquete.kaizen@gymforce.mx',
    'password': 'KaizenInt_2025_RPzM9y72jG5Qw48Lc1NtXb3',
    'max_workers': 3,  # hilos para peticiones async
    'timeout': (5, 10),  # (connect, read) timeout
    'retry_attempts': 2,
    'retry_delay': 1,  # segundos
}

# Configuración de logging
LOG_CONFIG = {
    'max_log_entries': 1000,  # máximo de entradas en el log UI
    'log_file': 'torniquete.log',
    'log_level': 'INFO',
}

# Configuración de la sucursal
SUCURSAL_CONFIG = {
    'sucursal_id': 1,  # ID de la sucursal por defecto
}
