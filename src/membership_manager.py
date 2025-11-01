import json
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from gymforce_api import GymforceAPI
from template_manager import TemplateManager


class MembershipManager:
    """Gestor automático de membresías con sincronización Gymforce y gestión de templates"""
    
    def __init__(self, data_file="memberships.json"):
        self.data_file = data_file
        self.users = {}  # {user_id: {name, expiration_date, status, last_visit, etc}}
        self.api = GymforceAPI()
        self.template_manager = TemplateManager()  # Nuevo: gestor de templates
        self.load_data()
    
    def load_data(self):
        """Carga datos de membresías desde archivo JSON"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
                print(f"[MembershipManager] ✅ Cargados {len(self.users)} usuarios")
            except Exception as e:
                print(f"[MembershipManager] ⚠️ Error cargando datos: {e}")
                self.users = {}
        else:
            print("[MembershipManager] 📝 Creando nuevo archivo de datos")
            self.users = {}
    
    def save_data(self):
        """Guarda datos de membresías a archivo JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=2, ensure_ascii=False)
            print(f"[MembershipManager] 💾 Guardados {len(self.users)} usuarios")
        except Exception as e:
            print(f"[MembershipManager] ❌ Error guardando datos: {e}")
    
    def validate_membership(self, user_id: str) -> Tuple[bool, str]:
        """
        Valida si un usuario tiene membresía activa
        Returns: (is_active, reason)
        """
        user_id = str(user_id).strip()
        
        # Si el usuario no existe en sistema local
        if user_id not in self.users:
            return False, "Usuario no registrado localmente"
        
        user = self.users[user_id]
        
        # Verificar estado
        if user.get('status') == 'inactive':
            return False, "Usuario inactivo"
        
        if user.get('status') == 'blocked':
            return False, "Usuario bloqueado temporalmente"
        
        # Verificar fecha de vencimiento
        expiration = user.get('expiration_date')
        if not expiration:
            return False, "Sin fecha de vencimiento"
        
        try:
            exp_date = datetime.strptime(expiration, "%Y-%m-%d")
            if datetime.now() > exp_date:
                # Marcar como vencido
                user['status'] = 'expired'
                self.save_data()
                return False, f"Membresía vencida desde {expiration}"
            else:
                # Actualizar última visita
                user['last_visit'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                user['visit_count'] = user.get('visit_count', 0) + 1
                self.save_data()
                return True, f"Membresía activa hasta {expiration}"
        except Exception as e:
            return False, f"Error validando fecha: {e}"
    
    def add_user(self, user_id: str, name: str, expiration_date: str, 
                 status: str = "active", **kwargs):
        """Agrega o actualiza un usuario"""
        user_id = str(user_id).strip()
        
        self.users[user_id] = {
            'user_id': user_id,
            'name': name,
            'expiration_date': expiration_date,
            'status': status,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_visit': None,
            'visit_count': 0,
            **kwargs
        }
        
        self.save_data()
        print(f"[MembershipManager] ✅ Usuario {user_id} agregado/actualizado")
    
    def update_expiration(self, user_id: str, new_expiration: str) -> bool:
        """Actualiza fecha de vencimiento de un usuario"""
        user_id = str(user_id).strip()
        
        if user_id not in self.users:
            return False
        
        self.users[user_id]['expiration_date'] = new_expiration
        self.users[user_id]['status'] = 'active'
        self.users[user_id]['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.save_data()
        print(f"[MembershipManager] ✅ Usuario {user_id} renovado hasta {new_expiration}")
        return True
    
    def block_user_with_backup(self, conn, user_id: str) -> bool:
        """
        Bloquea un usuario haciendo backup de sus templates faciales
        y eliminándolo del dispositivo temporalmente
        """
        user_id = str(user_id).strip()
        
        try:
            # Hacer backup de templates
            if self.template_manager.block_user(conn, user_id):
                # Actualizar estado en membresías
                if user_id in self.users:
                    self.users[user_id]['status'] = 'blocked'
                    self.users[user_id]['blocked_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_data()
                
                print(f"[MembershipManager] 🚫 Usuario {user_id} bloqueado (templates respaldados)")
                return True
            return False
        except Exception as e:
            print(f"[MembershipManager] ❌ Error bloqueando usuario: {e}")
            return False
    
    def unblock_user_with_restore(self, conn, user_id: str, new_expiration: Optional[str] = None) -> bool:
        """
        Desbloquea un usuario restaurando sus templates faciales
        """
        user_id = str(user_id).strip()
        
        try:
            # Restaurar templates
            if self.template_manager.unblock_user(conn, user_id):
                # Actualizar estado en membresías
                if user_id in self.users:
                    self.users[user_id]['status'] = 'active'
                    if new_expiration:
                        self.users[user_id]['expiration_date'] = new_expiration
                    self.users[user_id]['unblocked_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_data()
                
                print(f"[MembershipManager] ✅ Usuario {user_id} desbloqueado (templates restaurados)")
                return True
            return False
        except Exception as e:
            print(f"[MembershipManager] ❌ Error desbloqueando usuario: {e}")
            return False
    
    def deactivate_user(self, user_id: str):
        """Desactiva un usuario (no lo elimina del dispositivo)"""
        user_id = str(user_id).strip()
        
        if user_id in self.users:
            self.users[user_id]['status'] = 'inactive'
            self.users[user_id]['deactivated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_data()
            print(f"[MembershipManager] 🚫 Usuario {user_id} desactivado")
    
    def reactivate_user(self, user_id: str, new_expiration: Optional[str] = None):
        """Reactiva un usuario"""
        user_id = str(user_id).strip()
        
        if user_id in self.users:
            self.users[user_id]['status'] = 'active'
            if new_expiration:
                self.users[user_id]['expiration_date'] = new_expiration
            self.users[user_id]['reactivated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_data()
            print(f"[MembershipManager] ✅ Usuario {user_id} reactivado")
    
    def get_expired_users(self) -> list:
        """Obtiene lista de usuarios con membresía vencida"""
        expired = []
        today = datetime.now()
        
        for user_id, user in self.users.items():
            exp_date_str = user.get('expiration_date')
            if exp_date_str:
                try:
                    exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                    if today > exp_date and user.get('status') != 'blocked':
                        expired.append(user)
                except:
                    pass
        
        return expired
    
    def get_all_users(self) -> list:
        """Obtiene todos los usuarios"""
        return list(self.users.values())
    
    def sync_user_with_gymforce(self, user_id: str) -> bool:
        """Sincroniza un usuario con Gymforce"""
        try:
            result = self.api.validar_acceso(user_id)
            
            if result.get("access") == "allow":
                # Actualizar datos desde Gymforce
                self.update_user_from_gymforce(user_id, result)
                return True
            else:
                # Marcar como no permitido
                if user_id in self.users:
                    self.users[user_id]['gymforce_status'] = 'denied'
                    self.users[user_id]['gymforce_reason'] = result.get('respuesta', '')
                    self.save_data()
                return False
        except Exception as e:
            print(f"[MembershipManager] ❌ Error sincronizando {user_id}: {e}")
            return False
    
    def update_user_from_gymforce(self, user_id: str, gymforce_data: dict):
        """Actualiza usuario con datos de Gymforce"""
        user_id = str(user_id).strip()
        
        # Extraer datos relevantes de la respuesta de Gymforce
        name = gymforce_data.get('nombre', 'Desconocido')
        
        # Calcular fecha de vencimiento (ejemplo: 30 días desde hoy)
        # Ajusta esto según lo que retorne tu API
        expiration = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        if user_id not in self.users:
            self.add_user(
                user_id=user_id,
                name=name,
                expiration_date=expiration,
                status='active',
                gymforce_synced=True,
                gymforce_data=gymforce_data
            )
        else:
            self.users[user_id]['name'] = name
            self.users[user_id]['gymforce_synced'] = True
            self.users[user_id]['gymforce_data'] = gymforce_data
            self.users[user_id]['last_sync'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_data()
    
    def auto_block_expired(self, conn) -> int:
        """
        Bloquea automáticamente usuarios vencidos
        (hace backup de templates y los elimina del dispositivo)
        Returns: número de usuarios bloqueados
        """
        expired_users = self.get_expired_users()
        count = 0
        
        for user in expired_users:
            user_id = user['user_id']
            
            # Bloquear usuario (backup + eliminación)
            if self.block_user_with_backup(conn, user_id):
                count += 1
        
        return count
    
    def backup_all_templates(self, conn) -> int:
        """
        Hace backup de todos los templates del dispositivo
        Returns: número de usuarios respaldados
        """
        return self.template_manager.backup_all_users(conn)
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Obtiene información de un usuario"""
        return self.users.get(str(user_id).strip())
    
    def has_template_backup(self, user_id: str) -> bool:
        """Verifica si existe backup de templates para un usuario"""
        return self.template_manager.has_backup(str(user_id))