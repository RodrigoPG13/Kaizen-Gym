import json
import os
from datetime import datetime
from typing import List, Dict, Tuple
from template_manager import TemplateManager


class AutoBlockManager:
    """
    Sistema de bloqueo automático de usuarios vencidos
    Se ejecuta al iniciar el programa y bloquea automáticamente usuarios sin membresía activa
    """
    
    def __init__(self, templates_file="user_templates.json", memberships_file="memberships.json"):
        self.templates_file = templates_file
        self.memberships_file = memberships_file
        self.template_manager = TemplateManager(templates_file)
        self.memberships = {}
        self.auto_block_log = []
        
        # Cargar membresías
        self.load_memberships()
    
    def load_memberships(self):
        """Carga base de datos de membresías"""
        if os.path.exists(self.memberships_file):
            try:
                with open(self.memberships_file, 'r', encoding='utf-8') as f:
                    self.memberships = json.load(f)
                print(f"[AutoBlock] ✅ Cargadas {len(self.memberships)} membresías")
            except Exception as e:
                print(f"[AutoBlock] ⚠️ Error cargando membresías: {e}")
                self.memberships = {}
    
    def save_memberships(self):
        """Guarda base de datos de membresías"""
        try:
            with open(self.memberships_file, 'w', encoding='utf-8') as f:
                json.dump(self.memberships, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AutoBlock] ❌ Error guardando membresías: {e}")
    
    def sync_device_users_on_startup(self, conn) -> Tuple[int, int, int]:
        """
        Sincroniza usuarios del dispositivo con base de datos local al iniciar
        
        Returns:
            (total_users, backed_up, blocked)
        """
        print("\n" + "="*60)
        print("[AutoBlock] 🚀 INICIANDO SINCRONIZACIÓN AUTOMÁTICA")
        print("="*60)
        
        try:
            # Obtener todos los usuarios del dispositivo
            device_users = conn.get_users()
            total_users = len(device_users)
            
            print(f"[AutoBlock] 📊 Usuarios en dispositivo: {total_users}")
            
            backed_up = 0
            blocked = 0
            
            for user in device_users:
                user_id = str(user.user_id)
                
                # Verificar si ya tiene backup
                if not self.template_manager.has_backup(user_id):
                    # Hacer backup automáticamente
                    if self.template_manager.backup_user_templates(conn, user_id):
                        backed_up += 1
                        print(f"[AutoBlock] 💾 Backup: Usuario {user_id} ({user.name})")
                
                # Verificar si debe ser bloqueado
                should_block, reason = self.should_block_user(user_id)
                
                if should_block:
                    # Bloquear usuario
                    if self.block_user_automatically(conn, user_id, reason):
                        blocked += 1
                        print(f"[AutoBlock] 🚫 Bloqueado: Usuario {user_id} - {reason}")
            
            print("\n" + "="*60)
            print(f"[AutoBlock] ✅ SINCRONIZACIÓN COMPLETA")
            print(f"  • Usuarios totales: {total_users}")
            print(f"  • Backups creados: {backed_up}")
            print(f"  • Usuarios bloqueados: {blocked}")
            print("="*60 + "\n")
            
            return (total_users, backed_up, blocked)
            
        except Exception as e:
            print(f"[AutoBlock] ❌ Error en sincronización: {e}")
            return (0, 0, 0)
    
    def should_block_user(self, user_id: str) -> Tuple[bool, str]:
        """
        Determina si un usuario debe ser bloqueado
        
        Returns:
            (should_block, reason)
        """
        user_id = str(user_id)
        
        # Verificar si existe en base de membresías
        if user_id not in self.memberships:
            return False, "Usuario no registrado en sistema local"
        
        membership = self.memberships[user_id]
        
        # Verificar estado
        status = membership.get('status', 'unknown')
        
        if status == 'blocked':
            return True, "Ya está bloqueado"
        
        if status == 'inactive':
            return True, "Usuario inactivo"
        
        # Verificar fecha de vencimiento
        expiration_str = membership.get('expiration_date')
        
        if not expiration_str:
            return True, "Sin fecha de vencimiento"
        
        try:
            exp_date = datetime.strptime(expiration_str, "%Y-%m-%d")
            now = datetime.now()
            
            if now > exp_date:
                days_expired = (now - exp_date).days
                return True, f"Membresía vencida hace {days_expired} días"
            
            return False, "Membresía activa"
            
        except Exception as e:
            return True, f"Error en fecha: {e}"
    
    def block_user_automatically(self, conn, user_id: str, reason: str) -> bool:
        """
        Bloquea un usuario automáticamente
        """
        try:
            user_id = str(user_id)
            
            # Asegurar que hay backup
            if not self.template_manager.has_backup(user_id):
                if not self.template_manager.backup_user_templates(conn, user_id):
                    print(f"[AutoBlock] ⚠️ No se pudo hacer backup de {user_id}")
                    return False
            
            # Obtener usuario del dispositivo
            users = conn.get_users()
            user = next((u for u in users if str(u.user_id) == user_id), None)
            
            if not user:
                print(f"[AutoBlock] ⚠️ Usuario {user_id} no encontrado en dispositivo")
                return False
            
            # Eliminar del dispositivo
            conn.delete_user(uid=user.uid)
            
            # Actualizar estado en membresías
            if user_id in self.memberships:
                self.memberships[user_id]['status'] = 'blocked'
                self.memberships[user_id]['blocked_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.memberships[user_id]['block_reason'] = reason
                self.memberships[user_id]['auto_blocked'] = True
            
            self.save_memberships()
            
            # Log de bloqueo
            log_entry = {
                'user_id': user_id,
                'action': 'auto_block',
                'reason': reason,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.auto_block_log.append(log_entry)
            
            return True
            
        except Exception as e:
            print(f"[AutoBlock] ❌ Error bloqueando {user_id}: {e}")
            return False
    
    def unblock_user_automatically(self, conn, user_id: str, new_expiration: str) -> bool:
        """
        Desbloquea un usuario automáticamente cuando renueva
        """
        try:
            user_id = str(user_id)
            
            # Restaurar templates
            if not self.template_manager.restore_user_templates(conn, user_id):
                print(f"[AutoBlock] ❌ No se pudo restaurar templates de {user_id}")
                return False
            
            # Actualizar estado en membresías
            if user_id in self.memberships:
                self.memberships[user_id]['status'] = 'active'
                self.memberships[user_id]['expiration_date'] = new_expiration
                self.memberships[user_id]['unblocked_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.memberships[user_id]['auto_unblocked'] = True
            
            self.save_memberships()
            
            # Log de desbloqueo
            log_entry = {
                'user_id': user_id,
                'action': 'auto_unblock',
                'new_expiration': new_expiration,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.auto_block_log.append(log_entry)
            
            print(f"[AutoBlock] ✅ Usuario {user_id} desbloqueado hasta {new_expiration}")
            return True
            
        except Exception as e:
            print(f"[AutoBlock] ❌ Error desbloqueando {user_id}: {e}")
            return False
    
    def get_blocked_users(self) -> List[Dict]:
        """Obtiene lista de usuarios bloqueados"""
        blocked = []
        for user_id, membership in self.memberships.items():
            if membership.get('status') == 'blocked':
                blocked.append({
                    'user_id': user_id,
                    'name': membership.get('name', 'N/A'),
                    'blocked_at': membership.get('blocked_at', 'N/A'),
                    'reason': membership.get('block_reason', 'N/A')
                })
        return blocked
    
    def get_auto_block_log(self) -> List[Dict]:
        """Obtiene el log de bloqueos automáticos"""
        return self.auto_block_log.copy()
    
    def save_log(self, log_file="auto_block_log.json"):
        """Guarda el log de operaciones automáticas"""
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'last_sync': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'log': self.auto_block_log
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AutoBlock] ⚠️ Error guardando log: {e}")
    
    def check_and_block_expired_daily(self, conn) -> int:
        """
        Verifica y bloquea usuarios vencidos (para ejecutar diariamente)
        
        Returns:
            Número de usuarios bloqueados
        """
        print("\n[AutoBlock] 🔍 Verificación diaria de vencimientos...")
        
        device_users = conn.get_users()
        blocked_count = 0
        
        for user in device_users:
            user_id = str(user.user_id)
            should_block, reason = self.should_block_user(user_id)
            
            if should_block:
                if self.block_user_automatically(conn, user_id, reason):
                    blocked_count += 1
                    print(f"[AutoBlock] 🚫 Bloqueado: {user_id} - {reason}")
        
        print(f"[AutoBlock] ✅ Verificación completa: {blocked_count} usuarios bloqueados\n")
        return blocked_count
    
    def force_sync_all(self, conn) -> Dict:
        """
        Fuerza sincronización completa de todos los usuarios
        Útil para mantenimiento o después de cambios masivos
        """
        stats = {
            'total_device': 0,
            'total_local': len(self.memberships),
            'backed_up': 0,
            'blocked': 0,
            'errors': []
        }
        
        try:
            device_users = conn.get_users()
            stats['total_device'] = len(device_users)
            
            for user in device_users:
                user_id = str(user.user_id)
                
                # Backup si no existe
                if not self.template_manager.has_backup(user_id):
                    if self.template_manager.backup_user_templates(conn, user_id):
                        stats['backed_up'] += 1
                
                # Verificar bloqueo
                should_block, reason = self.should_block_user(user_id)
                if should_block:
                    if self.block_user_automatically(conn, user_id, reason):
                        stats['blocked'] += 1
        
        except Exception as e:
            stats['errors'].append(str(e))
        
        return stats