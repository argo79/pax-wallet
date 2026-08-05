"""
Settings View - Impostazioni completo
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("◈ IMPOSTAZIONI")
        title.setObjectName("view_title")
        layout.addWidget(title)
        
        # ========================================
        # SECURITY
        # ========================================
        pwd_group = QGroupBox("◈ CAMBIA PASSWORD")
        pwd_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        pwd_layout = QFormLayout(pwd_group)
        
        self.old_pwd = QLineEdit()
        self.old_pwd.setEchoMode(QLineEdit.Password)
        self.old_pwd.setPlaceholderText("> old password")
        self.new_pwd = QLineEdit()
        self.new_pwd.setEchoMode(QLineEdit.Password)
        self.new_pwd.setPlaceholderText("> new password")
        self.confirm_pwd = QLineEdit()
        self.confirm_pwd.setEchoMode(QLineEdit.Password)
        self.confirm_pwd.setPlaceholderText("> confirm password")
        
        pwd_layout.addRow("OLD:", self.old_pwd)
        pwd_layout.addRow("NEW:", self.new_pwd)
        pwd_layout.addRow("CONFIRM:", self.confirm_pwd)
        
        change_btn = QPushButton("◈ CAMBIA")
        change_btn.clicked.connect(self.change_password)
        pwd_layout.addRow("", change_btn)
        
        layout.addWidget(pwd_group)
        
        # ========================================
        # NETWORK - INTERNET / TOR TOGGLE
        # ========================================
        net_group = QGroupBox("◈ RETE")
        net_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        net_layout = QVBoxLayout(net_group)
        
        # Internet
        internet_layout = QHBoxLayout()
        internet_layout.addWidget(QLabel("INTERNET:"))
        self.internet_status = QLabel("?")
        self.internet_status.setObjectName("status")
        internet_layout.addWidget(self.internet_status)
        internet_layout.addStretch()
        self.internet_toggle = QPushButton("◈ TOGGLE")
        self.internet_toggle.clicked.connect(self.toggle_internet)
        internet_layout.addWidget(self.internet_toggle)
        net_layout.addLayout(internet_layout)
        
        # TOR
        tor_layout = QHBoxLayout()
        tor_layout.addWidget(QLabel("TOR:"))
        self.tor_status = QLabel("?")
        self.tor_status.setObjectName("status")
        tor_layout.addWidget(self.tor_status)
        tor_layout.addStretch()
        self.tor_toggle = QPushButton("◈ TOGGLE")
        self.tor_toggle.clicked.connect(self.toggle_tor)
        tor_layout.addWidget(self.tor_toggle)
        net_layout.addLayout(tor_layout)
        
        # TOR Port
        tor_port_layout = QHBoxLayout()
        tor_port_layout.addWidget(QLabel("TOR PORT:"))
        self.tor_port_input = QLineEdit()
        self.tor_port_input.setPlaceholderText("9050")
        self.tor_port_input.setFixedWidth(80)
        tor_port_layout.addWidget(self.tor_port_input)
        tor_port_layout.addStretch()
        tor_port_btn = QPushButton("◈ APPLICA")
        tor_port_btn.clicked.connect(self.set_tor_port)
        tor_port_layout.addWidget(tor_port_btn)
        net_layout.addLayout(tor_port_layout)
        
        layout.addWidget(net_group)
        
        # ========================================
        # CONFIG
        # ========================================
        config_group = QGroupBox("◈ CONFIGURAZIONE")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QFormLayout(config_group)
        
        self.config_display = QTextEdit()
        self.config_display.setReadOnly(True)
        self.config_display.setFont(QFont("Courier New", 9))
        self.config_display.setMaximumHeight(200)
        config_layout.addRow(self.config_display)
        
        reload_btn = QPushButton("◈ RICARICA CONFIG")
        reload_btn.clicked.connect(self.load_config)
        config_layout.addRow(reload_btn)
        
        layout.addWidget(config_group)
        
        # Status
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Carica status e config
        self.update_network_status()
        self.load_config()
    
    def load_config(self):
        """Carica e mostra il config"""
        try:
            import json
            from pathlib import Path
            config_path = Path("annuncio_config.json")
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                self.config_display.setText(json.dumps(config, indent=4))
                self.status_label.setText("✅ Config caricato")
            else:
                self.config_display.setText("⚠️ Config non trovato")
                self.status_label.setText("⚠️ Config non trovato")
        except Exception as e:
            self.config_display.setText(f"❌ Errore: {e}")
            self.status_label.setText(f"❌ Errore: {e}")
    
    def update_network_status(self):
        """Aggiorna status di Internet e TOR"""
        if not self.main.backend:
            return
        try:
            # Internet
            internet_on = self.main.backend.use_internet
            self.internet_status.setText("🌐 ON" if internet_on else "📡 OFF")
            self.internet_status.setStyleSheet("color: #00ff41;" if internet_on else "color: #ff6b6b;")
            
            # TOR
            tor_on = self.main.backend.use_tor
            self.tor_status.setText("🧅 ON" if tor_on else "OFF")
            self.tor_status.setStyleSheet("color: #00ff41;" if tor_on else "color: #ff6b6b;")
            
            # TOR Port
            self.tor_port_input.setText(str(self.main.backend.tor_socks_port))
            
        except Exception as e:
            self.status_label.setText(f"❌ Errore: {e}")
    
    def toggle_internet(self):
        """Toggle Internet ON/OFF"""
        if not self.main.backend:
            return
        current = self.main.backend.use_internet
        self.main.backend.set_use_internet(not current)
        self.update_network_status()
        if not current:
            self.status_label.setText("🌐 Internet attivato")
        else:
            self.status_label.setText("📡 Internet disattivato (usa Reticulum)")
    
    def toggle_tor(self):
        """Toggle TOR ON/OFF"""
        if not self.main.backend:
            return
        current = self.main.backend.use_tor
        self.main.backend.set_use_tor(not current)
        self.update_network_status()
        if not current:
            self.status_label.setText("🧅 TOR attivato")
        else:
            self.status_label.setText("🧅 TOR disattivato")
    
    def set_tor_port(self):
        """Imposta TOR port"""
        if not self.main.backend:
            return
        try:
            port = int(self.tor_port_input.text())
            self.main.backend.tor_socks_port = port
            self.main.backend._update_proxy()
            self.status_label.setText(f"✅ TOR port impostato a {port}")
        except ValueError:
            self.status_label.setText("❌ Porta non valida")
    
    def change_password(self):
        old = self.old_pwd.text()
        new = self.new_pwd.text()
        confirm = self.confirm_pwd.text()
        
        if new != confirm:
            self.status_label.setText("❌ > PASSWORDS DO NOT MATCH")
            return
        
        if len(new) < 4:
            self.status_label.setText("❌ > PASSWORD TOO SHORT")
            return
        
        try:
            result = self.main.backend.change_password(old, new)
            if result.get("success"):
                self.status_label.setText("✅ > PASSWORD CHANGED!")
                self.old_pwd.clear()
                self.new_pwd.clear()
                self.confirm_pwd.clear()
            else:
                self.status_label.setText(f"❌ > {result.get('message', 'UNKNOWN ERROR')}")
        except Exception as e:
            self.status_label.setText(f"❌ > {e}")