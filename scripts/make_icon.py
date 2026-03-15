#!/usr/bin/env python3
"""
Generiše app ikonu iz SVG-a.

Pokretanje (jednom, na macOS-u, prije build-a):
    python scripts/make_icon.py

Rezultat:
    assets/icon.icns  ← koristi PyInstaller

Zahtijeva:
    - PySide6 (već instalirano)
    - macOS (za iconutil koji kreira .icns)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SVG_PATH = BASE_DIR / "assets" / "icon.svg"
ICONSET_DIR = BASE_DIR / "assets" / "icon.iconset"
ICNS_PATH = BASE_DIR / "assets" / "icon.icns"
PNG_PATH = BASE_DIR / "assets" / "icon.png"

# Veličine koje macOS .icns zahtijeva
SIZES = [16, 32, 64, 128, 256, 512, 1024]


def svg_to_png(size: int, out_path: Path) -> None:
    """Renderuje SVG u PNG zadane veličine koristeći PySide6."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    # QApplication mora postojati za Qt operacije
    app = QApplication.instance() or QApplication(sys.argv[:1])

    svg_data = QByteArray(SVG_PATH.read_bytes())
    renderer = QSvgRenderer(svg_data)

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(0)  # Transparentno

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    image.save(str(out_path))
    print(f"  ✓ {out_path.name} ({size}x{size})")


def build_iconset() -> None:
    """Kreira iconset folder sa svim potrebnim veličinama."""
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        # Normalna rezolucija
        svg_to_png(size, ICONSET_DIR / f"icon_{size}x{size}.png")
        # Retina (@2x) — samo za veličine do 512
        if size <= 512:
            svg_to_png(size * 2, ICONSET_DIR / f"icon_{size}x{size}@2x.png")


def build_icns() -> None:
    """Poziva macOS iconutil za kreiranje .icns fajla."""
    if sys.platform != "darwin":
        print("⚠️  iconutil je dostupan samo na macOS. Preskačem .icns korak.")
        print(f"   PNG je sačuvan: {PNG_PATH}")
        return

    result = subprocess.run(
        ["iconutil", "--convert", "icns", str(ICONSET_DIR), "--output", str(ICNS_PATH)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"\n✅ Kreiran: {ICNS_PATH}")
    else:
        print(f"❌ iconutil greška: {result.stderr}")
        sys.exit(1)


def main() -> None:
    if not SVG_PATH.exists():
        print(f"❌ SVG nije pronađen: {SVG_PATH}")
        sys.exit(1)

    print(f"🎨 Generiše ikonu iz: {SVG_PATH.name}")
    print(f"   Iconset: {ICONSET_DIR}")

    # Generiši i 1024x1024 PNG (za preview)
    svg_to_png(1024, PNG_PATH)

    build_iconset()
    build_icns()

    # Počisti iconset folder (više nije potreban)
    if ICNS_PATH.exists():
        shutil.rmtree(ICONSET_DIR)
        print("   Iconset folder obrisan (više nije potreban)")


if __name__ == "__main__":
    main()
