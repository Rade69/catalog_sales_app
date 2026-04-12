"""
Autentikacioni dijalog za PIN/lozinku.
"""

import hashlib
import secrets
import json
import os
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon

from app.utils.paths import get_user_data_dir
from app.utils.logger import get_logger


class AuthDialog(QDialog):
    """Dijalog za autentikaciju sa PIN-om ili lozinkom."""
    
    authenticated = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = get_logger("auth")
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Podesi UI za autentikaciju."""
        self.setWindowTitle("Autentikacija")
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Naslov
        title_label = QLabel("Kataloška prodaja")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Podnaslov
        subtitle_label = QLabel("Unesite PIN za pristup aplikaciji")
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)
        
        # Polje za PIN
        self.pin_label = QLabel("PIN (4-6 cifara):")
        layout.addWidget(self.pin_label)
        
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setMaxLength(6)
        self.pin_input.setPlaceholderText("Unesite PIN")
        self.pin_input.returnPressed.connect(self.authenticate)
        layout.addWidget(self.pin_input)
        
        # Opcija za prikaz PIN-a
        self.show_pin_checkbox = QCheckBox("Prikaži PIN")
        self.show_pin_checkbox.toggled.connect(self.toggle_pin_visibility)
        layout.addWidget(self.show_pin_checkbox)
        
        # Dugmad
        button_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Prijavi se")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self.authenticate)
        button_layout.addWidget(self.login_button)
        
        self.cancel_button = QPushButton("Izađi")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def toggle_pin_visibility(self, checked: bool):
        """Prikaži/sakrij PIN."""
        if checked:
            self.pin_input.setEchoMode(QLineEdit.Normal)
        else:
            self.pin_input.setEchoMode(QLineEdit.Password)
    
    def load_config(self) -> bool:
        """Učitaj konfiguraciju autentikacije."""
        config_path = os.path.join(get_user_data_dir(), "auth_config.json")
        
        if not os.path.exists(config_path):
            # Prvo pokretanje - kreiraj novu konfiguraciju
            self.is_first_run = True
            self.pin_hash = None
            self.salt = None
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.is_first_run = False
            self.pin_hash = config.get("pin_hash")
            self.salt = config.get("salt")
            
            if not self.pin_hash or not self.salt:
                self.log.error("Nevalidna konfiguracija autentikacije")
                return False
                
            return True
            
        except Exception as e:
            self.log.error(f"Greška pri učitavanju konfiguracije: {e}")
            self.is_first_run = True
            self.pin_hash = None
            self.salt = None
            return False
    
    def save_config(self, pin: str) -> bool:
        """Sačuvaj konfiguraciju autentikacije."""
        try:
            # Generiši salt i hash za PIN
            salt = secrets.token_hex(16)
            pin_hash = self._hash_pin(pin, salt)
            
            config = {
                "pin_hash": pin_hash,
                "salt": salt,
                "created_at": os.path.getctime(__file__)
            }
            
            config_path = os.path.join(get_user_data_dir(), "auth_config.json")
            
            # Sačuvaj konfiguraciju
            with open(config_path, 'w') as f:
                json.dump(config, f)
            
            # Postavi permisije (samo vlasnik može čitati)
            os.chmod(config_path, 0o600)
            
            self.log.info("Konfiguracija autentikacije sačuvana")
            return True
            
        except Exception as e:
            self.log.error(f"Greška pri čuvanju konfiguracije: {e}")
            return False
    
    def _hash_pin(self, pin: str, salt: str) -> str:
        """Hash-uj PIN sa salt-om."""
        # Koristi PBKDF2 za sigurno hashovanje
        pin_bytes = pin.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        
        # 100,000 iteracija za sigurnost
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            pin_bytes,
            salt_bytes,
            100000
        )
        
        return hashed.hex()
    
    def verify_pin(self, pin: str) -> bool:
        """Proveri da li je PIN ispravan."""
        if not self.pin_hash or not self.salt:
            return False
        
        # Hash-uj uneti PIN sa postojećim salt-om
        test_hash = self._hash_pin(pin, self.salt)
        return secrets.compare_digest(test_hash, self.pin_hash)
    
    def authenticate(self):
        """Proces autentikacije."""
        pin = self.pin_input.text().strip()
        
        if not pin:
            self.show_error("Unesite PIN")
            return
        
        if len(pin) < 4 or len(pin) > 6:
            self.show_error("PIN mora imati 4-6 cifara")
            return
        
        if not pin.isdigit():
            self.show_error("PIN mora sadržati samo cifre")
            return
        
        if self.is_first_run:
            # Prvo pokretanje - postavi novi PIN
            if self.save_config(pin):
                self.show_success("PIN uspešno postavljen")
                self.accept()
                self.authenticated.emit()
            else:
                self.show_error("Greška pri čuvanju PIN-a")
        else:
            # Postojeći korisnik - proveri PIN
            if self.verify_pin(pin):
                self.show_success("Uspešna autentikacija")
                self.accept()
                self.authenticated.emit()
            else:
                self.show_error("Pogrešan PIN")
                self.pin_input.clear()
                self.pin_input.setFocus()
    
    def show_error(self, message: str):
        """Prikaži grešku."""
        self.status_label.setText(f"<font color='red'>{message}</font>")
        self.status_label.setStyleSheet("font-weight: bold;")
    
    def show_success(self, message: str):
        """Prikaži uspeh."""
        self.status_label.setText(f"<font color='green'>{message}</font>")
        self.status_label.setStyleSheet("font-weight: bold;")
    
    def closeEvent(self, event):
        """Rukovanje zatvaranjem dijaloga."""
        if self.is_first_run:
            # Na prvom pokretanju mora se postaviti PIN
            QMessageBox.warning(
                self,
                "PIN nije postavljen",
                "Morate postaviti PIN da biste koristili aplikaciju.\n\n"
                "Aplikacija će se zatvoriti."
            )
            self.reject()
        else:
            # Postojeći korisnik - pitaj da li želi da izađe
            reply = QMessageBox.question(
                self,
                "Izlazak iz aplikacije",
                "Da li ste sigurni da želite da izađete?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.reject()
            else:
                event.ignore()


def require_auth() -> bool:
    """
    Glavna funkcija za autentikaciju.
    Vraća True ako je autentikacija uspešna, False inače.
    """
    from PySide6.QtWidgets import QApplication
    
    app = QApplication.instance()
    if not app:
        # Ako aplikacija ne postoji, kreiraj je
        import sys
        app = QApplication(sys.argv)
    
    dialog = AuthDialog()
    result = dialog.exec()
    
    return result == QDialog.Accepted