from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QDateEdit, QComboBox,
    QHeaderView, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
from datetime import datetime, timedelta


class UserDashboard(QWidget):
    """Dashboard visual para gestión de usuarios y membresías"""
    
    def __init__(self, membership_manager, device_connection=None):
        super().__init__()
        self.membership_manager = membership_manager
        self.device_connection = device_connection  # Para operaciones en el dispositivo
        self.init_ui()
        self.refresh_table()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        layout = QVBoxLayout()
        
        # Sección de búsqueda y filtros
        search_layout = QHBoxLayout()
        
        search_layout.addWidget(QLabel("🔍 Buscar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ID o Nombre del usuario...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        
        search_layout.addWidget(QLabel("📊 Estado:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Todos", "Activos", "Vencidos", "Inactivos", "Bloqueados"])
        self.status_filter.currentTextChanged.connect(self.filter_table)
        search_layout.addWidget(self.status_filter)
        
        self.refresh_btn = QPushButton("🔄 Actualizar")
        self.refresh_btn.clicked.connect(self.refresh_table)
        search_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(search_layout)
        
        # Estadísticas rápidas
        stats_layout = QHBoxLayout()
        self.total_label = QLabel("Total: 0")
        self.active_label = QLabel("✅ Activos: 0")
        self.expired_label = QLabel("⚠️ Vencidos: 0")
        self.blocked_label = QLabel("🚫 Bloqueados: 0")
        
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.active_label)
        stats_layout.addWidget(self.expired_label)
        stats_layout.addWidget(self.blocked_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Tabla de usuarios
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Vencimiento", "Estado", "Visitas", "Última Visita", "Acciones"
        ])
        
        # Ajustar tamaño de columnas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.table)
        
        # Botones de acción
        action_layout = QHBoxLayout()
        
        self.add_user_btn = QPushButton("➕ Agregar Usuario")
        self.add_user_btn.clicked.connect(self.add_user_dialog)
        action_layout.addWidget(self.add_user_btn)
        
        self.renew_btn = QPushButton("🔄 Renovar Seleccionado")
        self.renew_btn.clicked.connect(self.renew_selected_user)
        action_layout.addWidget(self.renew_btn)
        
        self.cleanup_btn = QPushButton("🗑️ Limpiar Vencidos")
        self.cleanup_btn.clicked.connect(self.cleanup_expired)
        action_layout.addWidget(self.cleanup_btn)
        
        self.block_btn = QPushButton("🚫 Bloquear Seleccionado")
        self.block_btn.clicked.connect(self.block_selected_user)
        action_layout.addWidget(self.block_btn)
        
        self.backup_all_btn = QPushButton("💾 Backup de Todos")
        self.backup_all_btn.clicked.connect(self.backup_all_templates)
        action_layout.addWidget(self.backup_all_btn)
        
        action_layout.addStretch()
        
        layout.addLayout(action_layout)
        
        self.setLayout(layout)
    
    def refresh_table(self):
        """Actualiza la tabla con todos los usuarios"""
        users = self.membership_manager.get_all_users()
        self.populate_table(users)
        self.update_stats(users)
    
    def populate_table(self, users):
        """Llena la tabla con usuarios"""
        self.table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            # ID
            self.table.setItem(row, 0, QTableWidgetItem(user['user_id']))
            
            # Nombre
            self.table.setItem(row, 1, QTableWidgetItem(user.get('name', 'N/A')))
            
            # Vencimiento
            exp_date = user.get('expiration_date', 'N/A')
            exp_item = QTableWidgetItem(exp_date)
            
            # Colorear según estado
            status = user.get('status', 'unknown')
            if status == 'active':
                try:
                    exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
                    days_left = (exp_dt - datetime.now()).days
                    if days_left < 0:
                        exp_item.setBackground(QColor(255, 100, 100))  # Rojo (vencido)
                    elif days_left < 7:
                        exp_item.setBackground(QColor(255, 200, 100))  # Naranja (por vencer)
                    else:
                        exp_item.setBackground(QColor(100, 255, 100))  # Verde (activo)
                except:
                    pass
            elif status == 'expired':
                exp_item.setBackground(QColor(255, 100, 100))
            elif status == 'blocked':
                exp_item.setBackground(QColor(200, 100, 200))  # Morado (bloqueado)
            elif status == 'inactive':
                exp_item.setBackground(QColor(150, 150, 150))
            
            self.table.setItem(row, 2, exp_item)
            
            # Estado
            status_emoji = {
                'active': '✅ Activo',
                'expired': '⚠️ Vencido',
                'blocked': '🚫 Bloqueado',
                'inactive': '💤 Inactivo'
            }
            self.table.setItem(row, 3, QTableWidgetItem(status_emoji.get(status, status)))
            
            # Visitas
            visits = str(user.get('visit_count', 0))
            self.table.setItem(row, 4, QTableWidgetItem(visits))
            
            # Última visita
            last_visit = user.get('last_visit', 'Nunca')
            self.table.setItem(row, 5, QTableWidgetItem(last_visit))
            
            # Botón de acción
            action_btn = QPushButton("📝 Editar")
            action_btn.clicked.connect(lambda checked, uid=user['user_id']: self.edit_user(uid))
            self.table.setCellWidget(row, 6, action_btn)
    
    def update_stats(self, users):
        """Actualiza las estadísticas"""
        total = len(users)
        active = sum(1 for u in users if u.get('status') == 'active')
        expired = sum(1 for u in users if u.get('status') == 'expired')
        blocked = sum(1 for u in users if u.get('status') == 'blocked')
        
        self.total_label.setText(f"📊 Total: {total}")
        self.active_label.setText(f"✅ Activos: {active}")
        self.expired_label.setText(f"⚠️ Vencidos: {expired}")
        self.blocked_label.setText(f"🚫 Bloqueados: {blocked}")
    
    def filter_table(self):
        """Filtra la tabla según búsqueda y filtros"""
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()
        
        users = self.membership_manager.get_all_users()
        
        # Aplicar filtros
        filtered_users = []
        for user in users:
            # Filtro de búsqueda
            if search_text:
                if search_text not in user['user_id'].lower() and \
                   search_text not in user.get('name', '').lower():
                    continue
            
            # Filtro de estado
            if status_filter != "Todos":
                if status_filter == "Activos" and user.get('status') != 'active':
                    continue
                elif status_filter == "Vencidos" and user.get('status') != 'expired':
                    continue
                elif status_filter == "Inactivos" and user.get('status') != 'inactive':
                    continue
                elif status_filter == "Bloqueados" and user.get('status') != 'blocked':
                    continue
            
            filtered_users.append(user)
        
        self.populate_table(filtered_users)
        self.update_stats(filtered_users)
    
    def add_user_dialog(self):
        """Diálogo para agregar nuevo usuario"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Usuario")
        dialog.resize(400, 250)
        
        layout = QFormLayout()
        
        user_id_input = QLineEdit()
        name_input = QLineEdit()
        
        exp_date_input = QDateEdit()
        exp_date_input.setDate(QDate.currentDate().addMonths(1))
        exp_date_input.setCalendarPopup(True)
        
        layout.addRow("ID Usuario:", user_id_input)
        layout.addRow("Nombre:", name_input)
        layout.addRow("Fecha Vencimiento:", exp_date_input)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addRow(buttons)
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_id = user_id_input.text().strip()
            name = name_input.text().strip()
            exp_date = exp_date_input.date().toString("yyyy-MM-dd")
            
            if user_id and name:
                self.membership_manager.add_user(user_id, name, exp_date)
                self.refresh_table()
                QMessageBox.information(self, "Éxito", f"Usuario {user_id} agregado correctamente")
            else:
                QMessageBox.warning(self, "Error", "Debes completar todos los campos")
    
    def edit_user(self, user_id):
        """Edita un usuario existente"""
        user = self.membership_manager.get_user_info(user_id)
        if not user:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Editar Usuario {user_id}")
        dialog.resize(400, 250)
        
        layout = QFormLayout()
        
        name_input = QLineEdit(user.get('name', ''))
        
        exp_date_str = user.get('expiration_date', '')
        exp_date_input = QDateEdit()
        if exp_date_str:
            exp_date_input.setDate(QDate.fromString(exp_date_str, "yyyy-MM-dd"))
        exp_date_input.setCalendarPopup(True)
        
        status_combo = QComboBox()
        status_combo.addItems(['active', 'expired', 'inactive', 'blocked'])
        status_combo.setCurrentText(user.get('status', 'active'))
        
        layout.addRow("Nombre:", name_input)
        layout.addRow("Fecha Vencimiento:", exp_date_input)
        layout.addRow("Estado:", status_combo)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addRow(buttons)
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            exp_date = exp_date_input.date().toString("yyyy-MM-dd")
            status = status_combo.currentText()
            
            self.membership_manager.add_user(user_id, name, exp_date, status)
            
            # Si cambió a activo y estaba bloqueado, intentar restaurar
            if status == 'active' and user.get('status') == 'blocked':
                if self.device_connection:
                    if self.membership_manager.unblock_user_with_restore(self.device_connection, user_id, exp_date):
                        QMessageBox.information(self, "Éxito", f"Usuario {user_id} desbloqueado y restaurado")
                    else:
                        QMessageBox.warning(self, "Advertencia", f"Usuario actualizado pero no se pudo restaurar en el dispositivo")
            
            self.refresh_table()
            QMessageBox.information(self, "Éxito", f"Usuario {user_id} actualizado")
    
    def renew_selected_user(self):
        """Renueva el usuario seleccionado"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Advertencia", "Selecciona un usuario primero")
            return
        
        row = selected_rows[0].row()
        user_id = self.table.item(row, 0).text()
        
        # Calcular nueva fecha (30 días desde hoy)
        new_expiration = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        reply = QMessageBox.question(
            self,
            "Confirmar Renovación",
            f"¿Renovar membresía del usuario {user_id} hasta {new_expiration}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            user = self.membership_manager.get_user_info(user_id)
            
            # Si estaba bloqueado, desbloquear
            if user and user.get('status') == 'blocked':
                if self.device_connection:
                    if self.membership_manager.unblock_user_with_restore(self.device_connection, user_id, new_expiration):
                        self.refresh_table()
                        QMessageBox.information(self, "Éxito", f"Usuario {user_id} renovado y desbloqueado hasta {new_expiration}")
                    else:
                        QMessageBox.warning(self, "Error", "No se pudo desbloquear el usuario")
                else:
                    QMessageBox.warning(self, "Sin conexión", "Conéctate al dispositivo para desbloquear usuarios")
            else:
                self.membership_manager.update_expiration(user_id, new_expiration)
                self.refresh_table()
                QMessageBox.information(self, "Éxito", f"Usuario {user_id} renovado hasta {new_expiration}")
    
    def cleanup_expired(self):
        """Limpia usuarios vencidos"""
        expired = self.membership_manager.get_expired_users()
        
        if not expired:
            QMessageBox.information(self, "Info", "No hay usuarios vencidos")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirmar Limpieza",
            f"Se marcarán como inactivos {len(expired)} usuarios vencidos.\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for user in expired:
                self.membership_manager.deactivate_user(user['user_id'])
            
            self.refresh_table()
            QMessageBox.information(self, "Éxito", f"{len(expired)} usuarios marcados como inactivos")
    
    def block_selected_user(self):
        """Bloquea el usuario seleccionado (hace backup y elimina del dispositivo)"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Advertencia", "Selecciona un usuario primero")
            return
        
        # Verificar que haya conexión al dispositivo
        if not self.device_connection:
            QMessageBox.warning(
                self,
                "Sin conexión",
                "Debes estar conectado al dispositivo para bloquear usuarios.\n\nVe a la pestaña 'Monitor de Accesos' y conéctate primero."
            )
            return
        
        row = selected_rows[0].row()
        user_id = self.table.item(row, 0).text()
        user_name = self.table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self,
            "Confirmar Bloqueo",
            f"¿Bloquear al usuario {user_id} ({user_name})?\n\n"
            f"✅ Se hará backup de sus datos biométricos\n"
            f"✅ Se eliminará temporalmente del dispositivo\n"
            f"✅ Se podrá restaurar cuando renueve\n\n"
            f"El usuario NO podrá acceder hasta que se reactive.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Bloquear usuario
            if self.membership_manager.block_user_with_backup(self.device_connection, user_id):
                self.refresh_table()
                QMessageBox.information(
                    self,
                    "Usuario Bloqueado",
                    f"✅ Usuario {user_id} bloqueado correctamente\n\n"
                    f"• Templates faciales respaldados\n"
                    f"• Usuario eliminado del dispositivo\n"
                    f"• Se puede restaurar cuando renueve"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"❌ No se pudo bloquear al usuario {user_id}\n\nVerifica la conexión al dispositivo."
                )
    
    def backup_all_templates(self):
        """Hace backup de todos los templates del dispositivo"""
        if not self.device_connection:
            QMessageBox.warning(
                self,
                "Sin conexión",
                "Debes estar conectado al dispositivo.\n\nVe a la pestaña 'Monitor de Accesos' y conéctate primero."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Backup Completo",
            "¿Hacer backup de TODOS los usuarios del dispositivo?\n\n"
            "Esto guardará los templates faciales de todos los usuarios localmente.\n"
            "Es recomendable hacer esto antes de bloquear usuarios masivamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            count = self.membership_manager.backup_all_templates(self.device_connection)
            QMessageBox.information(
                self,
                "Backup Completo",
                f"✅ Backup completado\n\n"
                f"Templates respaldados: {count} usuarios\n\n"
                f"Los datos están guardados en 'user_templates.json'"
            )
    
    def set_device_connection(self, conn):
        """Actualiza la referencia a la conexión del dispositivo"""
        self.device_connection = conn
    
    def update_user_status(self, user_id: str, allowed: bool, reason: str):
        """Actualiza el estado de un usuario en tiempo real"""
        # Buscar el usuario en la tabla y actualizar
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == user_id:
                # Actualizar última visita
                self.table.setItem(row, 5, QTableWidgetItem(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                break