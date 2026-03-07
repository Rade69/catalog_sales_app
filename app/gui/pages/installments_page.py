from PySide6.QtWidgets import QWidget

from app.gui.pages.simple_pages import CrudPreviewPage


class InstallmentsPage(CrudPreviewPage):
    def __init__(self) -> None:
        super().__init__(
            title="Rate",
            form_labels=["Narudžba", "Rata broj", "Datum dospijeća", "Iznos", "Status"],
            table_headers=["Kupac", "Artikal", "Rata", "Dospijeće", "Status", "Iznos"],
            sample_rows=[
                ["Milica Petrović", "Blender Philips", "3/5", "15.03.2026", "Na čekanju", "20 KM"],
                ["Jelena Savić", "Tava set", "2/4", "20.03.2026", "Kasni", "35 KM"],
            ],
        )

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira - osvježava podatke."""
        pass  # Placeholder za buduću implementaciju
