"""
Global Stylesheet Loader

Učitava globalni QSS stylesheet za cijelu aplikaciju.
"""

from pathlib import Path


def load_stylesheet() -> str:
    """
    Učitava globalni stylesheet iz app_style.qss fajla.
    
    Returns:
        Sadržaj QSS fajla kao string
    """
    styles_dir = Path(__file__).parent
    qss_path = styles_dir / "app_style.qss"
    
    if not qss_path.exists():
        # Fallback na prazan stylesheet ako fajl ne postoji
        return ""
    
    with open(qss_path, "r", encoding="utf-8") as f:
        return f.read()


# Globalna varijabla za stylesheet
APP_STYLESHEET = load_stylesheet()
