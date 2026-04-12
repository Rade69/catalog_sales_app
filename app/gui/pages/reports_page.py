from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.base_page import BasePage


class ReportsPage(BasePage):
    """
    Stranica za generiranje Excel izvještaja naplate.

    Sadrži samo jedan alat: generator kompleksnog Excel-a
    u formatu 'Evidencija o uplatama rata' (po uzoru na ODS original).
    """

    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        root.addWidget(self._build_naplata_card())
        root.addStretch(1)

        self._load_campaigns_combo()

    def on_activate(self) -> None:
        self._load_campaigns_combo()

    def on_deactivate(self) -> None:
        # Cleanup any resources if needed
        pass

    def _build_naplata_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Naslov
        title = QLabel("Izvještaj naplate — Excel")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        desc = QLabel(
            "Generira Excel izvještaj u formatu 'Evidencija o uplatama rata'. "
            "Sadrži sve narudžbe odabrane kampanje sa plaćenim i preostalim ratama, "
            "datumima dospijeća i brojevima ugovora."
        )
        desc.setWordWrap(True)
        desc.setProperty("helpText", True)
        layout.addWidget(desc)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setProperty("separator", True)
        layout.addWidget(sep)

        # Kampanja
        kampanja_row = QHBoxLayout()
        kampanja_lbl = QLabel("Kampanja:")
        kampanja_lbl.setFixedWidth(130)
        self.report_campaign_combo = QComboBox()
        self.report_campaign_combo.setMinimumWidth(280)
        kampanja_row.addWidget(kampanja_lbl)
        kampanja_row.addWidget(self.report_campaign_combo)
        kampanja_row.addStretch(1)
        layout.addLayout(kampanja_row)

        # Saradnički broj
        kod_row = QHBoxLayout()
        kod_lbl = QLabel("Saradnički broj:")
        kod_lbl.setFixedWidth(130)
        self.agent_code_edit = QLineEdit()
        self.agent_code_edit.setPlaceholderText("npr. 4-1-11-2-1-3")
        self.agent_code_edit.setMaximumWidth(180)
        kod_row.addWidget(kod_lbl)
        kod_row.addWidget(self.agent_code_edit)
        kod_row.addStretch(1)
        layout.addLayout(kod_row)

        # Ime saradnika
        ime_row = QHBoxLayout()
        ime_lbl = QLabel("Ime saradnika:")
        ime_lbl.setFixedWidth(130)
        self.agent_name_edit = QLineEdit()
        self.agent_name_edit.setText("KRUNIĆ STOJANOVIĆ SANJA")
        self.agent_name_edit.setMinimumWidth(280)
        ime_row.addWidget(ime_lbl)
        ime_row.addWidget(self.agent_name_edit)
        ime_row.addStretch(1)
        layout.addLayout(ime_row)

        # Dugme
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("📊  Generiraj Excel izvještaj")
        self.btn_generate.setProperty("generateBtn", True)
        self.btn_generate.setMinimumHeight(48)
        self.btn_generate.clicked.connect(self._generate_naplata_report)
        btn_row.addWidget(self.btn_generate)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Status label
        self.report_status_label = QLabel("")
        self.report_status_label.setWordWrap(True)
        self.report_status_label.setVisible(False)
        layout.addWidget(self.report_status_label)

        return card

    def _load_campaigns_combo(self) -> None:
        from app.services.campaign_service import CampaignService
        try:
            campaigns = CampaignService.list_campaigns()
            self.report_campaign_combo.clear()
            for c in campaigns:
                self.report_campaign_combo.addItem(c.name, userData=c.id)
        except Exception:
            pass

    def _generate_naplata_report(self) -> None:
        from app.reports.naplata_report import generate_naplata_excel

        campaign_id = self.report_campaign_combo.currentData()
        if campaign_id is None:
            self._show_error_message("Odaberi kampanju.")
            return

        campaign_name = self.report_campaign_combo.currentText()
        safe_name = campaign_name.replace(" ", "_").replace("/", "-")
        default_filename = f"Naplata_{safe_name}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Spremi Excel izvještaj",
            str(Path.home() / default_filename),
            "Excel fajlovi (*.xlsx)"
        )
        if not save_path:
            return

        try:
            self.btn_generate.setEnabled(False)
            self.btn_generate.setText("Generisanje...")

            output = generate_naplata_excel(
                campaign_id=campaign_id,
                output_path=Path(save_path),
                agent_code=self.agent_code_edit.text().strip(),
                agent_name=self.agent_name_edit.text().strip()
                           or "KRUNIĆ STOJANOVIĆ SANJA",
            )

            self._show_success_message(f"Izvještaj uspješno generisan:\n{output}", use_banner=True)

        except Exception as e:
            self._show_error_message(f"Greška pri generisanju izvještaja:\n{str(e)}", use_banner=True)
        finally:
            self.btn_generate.setEnabled(True)
            self.btn_generate.setText("📊  Generiraj Excel izvještaj")
