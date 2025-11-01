import json
import os
from typing import List, Dict, Optional


class TemplateManager:
    """
    Gestor de templates biométricos (huellas/rostros)
    Permite eliminar usuarios temporalmente sin perder sus datos biométricos
    """
    
    def __init__(self, templates_file="user_templates.json"):
        self.templates_file = templates_file
        self.templates_db = {}  # {user_id: {'user': user_data, 'templates': [template_data]}}
        self.load_templates()
    
    def load_templates(self):
        """Carga templates desde archivo JSON"""
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    self.templates_db = json.load(f)
                print(f"[TemplateManager] ✅ Cargados templates de {len(self.templates_db)} usuarios")
            except Exception as e:
                print(f"[TemplateManager] ⚠️ Error cargando templates: {e}")
                self.templates_db = {}
        else:
            print("[TemplateManager] 📝 Creando nueva base de templates")
            self.templates_db = {}
    
    def save_templates(self):
        """Guarda templates a archivo JSON"""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates_db, f, indent=2, ensure_ascii=False)
            print(f"[TemplateManager] 💾 Guardados templates de {len(self.templates_db)} usuarios")
        except Exception as e:
            print(f"[TemplateManager] ❌ Error guardando templates: {e}")
    
    def backup_user_templates(self, conn, user_id: str) -> bool:
        """
        Descarga y guarda los templates de un usuario del dispositivo
        Args:
            conn: Conexión al dispositivo ZK
            user_id: ID del usuario
        Returns:
            True si fue exitoso
        """
        try:
            from zk.user import User
            
            # Obtener información del usuario
            users = conn.get_users()
            user = next((u for u in users if str(u.user_id) == str(user_id)), None)
            
            if not user:
                print(f"[TemplateManager] ⚠️ Usuario {user_id} no encontrado en dispositivo")
                return False
            
            # Obtener templates del usuario
            # Para dispositivos de reconocimiento facial, esto obtiene los templates faciales
            all_templates = conn.get_templates()
            user_templates = [t for t in all_templates if t.uid == user.uid]
            
            if not user_templates:
                print(f"[TemplateManager] ⚠️ Usuario {user_id} no tiene templates")
                return False
            
            # Guardar en base de datos local
            self.templates_db[str(user_id)] = {
                'user': {
                    'uid': user.uid,
                    'name': user.name,
                    'privilege': user.privilege,
                    'password': user.password,
                    'group_id': user.group_id,
                    'user_id': user.user_id,
                    'card': user.card
                },
                'templates': [
                    {
                        'uid': t.uid,
                        'fid': t.fid,
                        'valid': t.valid,
                        'template': t.template.hex() if hasattr(t.template, 'hex') else str(t.template),
                        'mark': t.mark if hasattr(t, 'mark') else ''
                    }
                    for t in user_templates
                ]
            }
            
            self.save_templates()
            print(f"[TemplateManager] ✅ Backup de {len(user_templates)} templates para usuario {user_id}")
            return True
            
        except Exception as e:
            print(f"[TemplateManager] ❌ Error en backup de templates: {e}")
            return False
    
    def restore_user_templates(self, conn, user_id: str) -> bool:
        """
        Restaura los templates de un usuario al dispositivo
        Args:
            conn: Conexión al dispositivo ZK
            user_id: ID del usuario
        Returns:
            True si fue exitoso
        """
        try:
            from zk.user import User
            from zk.finger import Finger
            
            user_id_str = str(user_id)
            
            if user_id_str not in self.templates_db:
                print(f"[TemplateManager] ⚠️ No hay backup para usuario {user_id}")
                return False
            
            backup = self.templates_db[user_id_str]
            
            # Recrear objeto User
            user_data = backup['user']
            user = User(
                uid=user_data['uid'],
                name=user_data['name'],
                privilege=user_data['privilege'],
                password=user_data['password'],
                group_id=user_data['group_id'],
                user_id=user_data['user_id'],
                card=user_data.get('card', 0)
            )
            
            # Recrear objetos Finger/Template
            templates = []
            for t_data in backup['templates']:
                template_bytes = bytes.fromhex(t_data['template']) if isinstance(t_data['template'], str) else t_data['template']
                
                finger = Finger(
                    uid=t_data['uid'],
                    fid=t_data['fid'],
                    valid=t_data['valid'],
                    template=template_bytes
                )
                templates.append(finger)
            
            # Subir al dispositivo
            conn.save_user_template(user, templates)
            
            print(f"[TemplateManager] ✅ Restaurados {len(templates)} templates para usuario {user_id}")
            return True
            
        except Exception as e:
            print(f"[TemplateManager] ❌ Error restaurando templates: {e}")
            return False
    
    def backup_all_users(self, conn) -> int:
        """
        Hace backup de todos los usuarios del dispositivo
        Returns:
            Número de usuarios respaldados
        """
        try:
            users = conn.get_users()
            count = 0
            
            for user in users:
                if self.backup_user_templates(conn, str(user.user_id)):
                    count += 1
            
            print(f"[TemplateManager] ✅ Backup completo: {count}/{len(users)} usuarios")
            return count
            
        except Exception as e:
            print(f"[TemplateManager] ❌ Error en backup masivo: {e}")
            return 0
    
    def has_backup(self, user_id: str) -> bool:
        """Verifica si existe backup para un usuario"""
        return str(user_id) in self.templates_db
    
    def get_backup_info(self, user_id: str) -> Optional[Dict]:
        """Obtiene información del backup de un usuario"""
        return self.templates_db.get(str(user_id))
    
    def delete_backup(self, user_id: str) -> bool:
        """Elimina el backup de un usuario"""
        user_id_str = str(user_id)
        if user_id_str in self.templates_db:
            del self.templates_db[user_id_str]
            self.save_templates()
            print(f"[TemplateManager] 🗑️ Backup eliminado para usuario {user_id}")
            return True
        return False
    
    def block_user(self, conn, user_id: str) -> bool:
        """
        Bloquea un usuario (hace backup y lo elimina del dispositivo)
        Args:
            conn: Conexión al dispositivo ZK
            user_id: ID del usuario
        Returns:
            True si fue exitoso
        """
        try:
            # Primero hacer backup
            if not self.backup_user_templates(conn, user_id):
                print(f"[TemplateManager] ❌ No se pudo hacer backup antes de bloquear")
                return False
            
            # Obtener UID para eliminar
            users = conn.get_users()
            user = next((u for u in users if str(u.user_id) == str(user_id)), None)
            
            if not user:
                print(f"[TemplateManager] ⚠️ Usuario {user_id} no encontrado")
                return False
            
            # Eliminar del dispositivo
            conn.delete_user(uid=user.uid)
            
            print(f"[TemplateManager] 🚫 Usuario {user_id} bloqueado (eliminado temporalmente)")
            return True
            
        except Exception as e:
            print(f"[TemplateManager] ❌ Error bloqueando usuario: {e}")
            return False
    
    def unblock_user(self, conn, user_id: str) -> bool:
        """
        Desbloquea un usuario (restaura desde backup)
        Args:
            conn: Conexión al dispositivo ZK
            user_id: ID del usuario
        Returns:
            True si fue exitoso
        """
        return self.restore_user_templates(conn, user_id)
    
    def list_backups(self) -> List[Dict]:
        """Lista todos los backups disponibles"""
        return [
            {
                'user_id': uid,
                'name': data['user']['name'],
                'templates_count': len(data['templates'])
            }
            for uid, data in self.templates_db.items()
        ]