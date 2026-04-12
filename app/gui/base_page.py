from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QFrame,
)

from app.gui.icons import get_pixmap


class BasePage(QWidget):
    """
    Bazna klasa za sve GUI stranice sa unificiranim pattern-ima za:
    - Loading stanje
    - Error handling
    - Success notifikacije
    - Status banner-e
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loading_label: Optional[QLabel] = None
        self._status_banner: Optional[QLabel] = None

    def _init_loading_label(self) -> None:
        """Inicijalizuje loading label ako nije već postavljen."""
        if not self._loading_label:
            self._loading_label = QLabel("Učitavanje...")
            self._loading_label.setProperty("loading", True)
            self._loading_label.setAlignment(Qt.AlignCenter)
            self._loading_label.hide()

    def _init_status_banner(self) -> None:
        """Inicijalizuje status banner ako nije već postavljen."""
        if not self._status_banner:
            self._status_banner = QLabel("")
            self._status_banner.setWordWrap(True)
            self._status_banner.setVisible(False)
            self._status_banner.setProperty("statusBanner", "info")

    def _set_loading_state(self, loading: bool, message: str = "Učitavanje...") -> None:
        """
        Postavlja UI u loading stanje.
        
        Args:
            loading: True za prikaz loading-a, False za sakrivanje
            message: Poruka koja se prikazuje (opciono)
        """
        if not self._loading_label:
            self._init_loading_label()
        
        if loading:
            self._loading_label.setText(message)
            self._loading_label.show()
            self._set_widgets_enabled(False)
        else:
            self._loading_label.hide()
            self._set_widgets_enabled(True)

    def _set_widgets_enabled(self, enabled: bool) -> None:
        """
        Onemogućava ili omogućava interaktivne widget-e.
        Override-uj u podklasama za specifične widget-e.
        """
        pass

    def _show_error_message(self, title: str, message: str, use_banner: bool = False) -> None:
        """
        Prikazuje grešku koristeći QMessageBox ili status banner.
        
        Args:
            title: Naslov dijaloga
            message: Poruka greške
            use_banner: True za korišćenje status banner-a umesto QMessageBox-a
        """
        if use_banner:
            self._show_status_banner(message, "error")
        else:
            QMessageBox.critical(self, title, message)

    def _show_success_message(self, title: str, message: str, use_banner: bool = False) -> None:
        """
        Prikazuje uspješnu poruku koristeći QMessageBox ili status banner.
        
        Args:
            title: Naslov dijaloga
            message: Poruka
            use_banner: True za korišćenje status banner-a umesto QMessageBox-a
        """
        if use_banner:
            self._show_status_banner(message, "success")
        else:
            QMessageBox.information(self, title, message)

    def _show_warning_message(self, title: str, message: str, use_banner: bool = False) -> None:
        """
        Prikazuje upozorenje koristeći QMessageBox ili status banner.
        
        Args:
            title: Naslov dijaloga
            message: Poruka upozorenja
            use_banner: True za korišćenje status banner-a umesto QMessageBox-a
        """
        if use_banner:
            self._show_status_banner(message, "warning")
        else:
            QMessageBox.warning(self, title, message)

    def _show_status_banner(self, message: str, banner_type: str = "info") -> None:
        """
        Prikazuje status banner sa porukom.
        
        Args:
            message: Poruka za prikaz
            banner_type: "success", "error", "warning", ili "info"
        """
        if not self._status_banner:
            self._init_status_banner()
        
        self._status_banner.setText(message)
        self._status_banner.setProperty("statusBanner", banner_type)
        self._status_banner.style().unpolish(self._status_banner)
        self._status_banner.style().polish(self._status_banner)
        self._status_banner.setVisible(True)

    def _hide_status_banner(self) -> None:
        """Sakriva status banner."""
        if self._status_banner:
            self._status_banner.setVisible(False)

    def _create_loading_section(self) -> QFrame:
        """
        Kreira sekciju za loading koji se može dodati u layout.
        
        Returns:
            QFrame sa loading label-om
        """
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 20, 0, 20)
        
        self._init_loading_label()
        layout.addWidget(self._loading_label)
        
        return frame

    def _create_status_banner_section(self) -> QFrame:
        """
        Kreira sekciju za status banner koji se može dodati u layout.
        
        Returns:
            QFrame sa status banner-om
        """
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._init_status_banner()
        layout.addWidget(self._status_banner)
        
        return frame

    def _confirm_action(self, title: str, message: str) -> bool:
        """
        Prikazuje dijalog za potvrdu akcije.
        
        Args:
            title: Naslov dijaloga
            message: Poruka za potvrdu
            
        Returns:
            True ako je korisnik potvrdio, False ako je odustao
        """
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def _show_loading_overlay(self, message: str = "Učitavanje...") -> None:
        """
        Prikazuje overlay za dugotrajne operacije.
        Koristi se za operacije koje traju duže od 2-3 sekunde.
        """
        # Ova metoda može biti implementirana ako je potrebno
        # za kompleksnije loading overlay-e
        self._set_loading_state(True, message)

    def _hide_loading_overlay(self) -> None:
        """Sakriva loading overlay."""
        self._set_loading_state(False)

    def on_activate(self) -> None:
        """
        Poziva se kada se stranica aktivira.
        Override-uj u podklasama za osvježavanje podataka.
        """
        pass

    def on_deactivate(self) -> None:
        """
        Poziva se kada se stranica deaktivira.
        Override-uj u podklasama za cleanup.
        """
        pass