#!/usr/bin/env bash
# =============================================================================
# build_macos.sh — Build macOS .app bundle za Katalošku prodaju
# =============================================================================
# Preduvjeti:
#   - macOS (Apple Silicon ili Intel)
#   - Python 3.11+ instaliran (preporučeno: brew install python@3.11)
#   - Pokrenuti jednom: pip install -r requirements.txt pyinstaller
#
# Upotreba:
#   chmod +x build_macos.sh
#   ./build_macos.sh
#
# Rezultat:
#   dist/Kataloška prodaja.app  ← ovo kopiraš u /Applications
# =============================================================================

set -e

echo "========================================"
echo "  Build: Kataloška prodaja.app"
echo "========================================"

# Provjeri da li postoji pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: pyinstaller nije instaliran."
    echo "Pokreni: pip install pyinstaller"
    exit 1
fi

# Generiši ikonu ako ICNS ne postoji
if [ ! -f "assets/icon.icns" ]; then
    echo "→ Generiše ikonu (assets/icon.icns)..."
    python scripts/make_icon.py
else
    echo "→ Ikonica već postoji (assets/icon.icns)"
fi

# Očisti stare buildove
echo "→ Čistim stare buildove..."
rm -rf dist/KataloškaProdaja dist/"Kataloška prodaja.app" build/KataloškaProdaja __pycache__

# Build
echo "→ Pokretam PyInstaller..."
pyinstaller katalog.spec --noconfirm --clean

echo ""
echo "========================================"
echo "  ✅ Build gotov!"
echo "  App: dist/Kataloška prodaja.app"
echo ""
echo "  Kopiraj u Applications:"
echo "  cp -r 'dist/Kataloška prodaja.app' /Applications/"
echo "========================================"
