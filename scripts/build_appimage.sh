#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[INFO]${NC} Starting AXIOM Pro AppImage Build Process..."

# Ensure running from project root
if [ ! -f "main.py" ] || [ ! -d "scripts" ]; then
    echo -e "${RED}[ERROR]${NC} Please run this script from the project root directory."
    exit 1
fi

# 1. Setup & Compilation (PyInstaller)
echo -e "${BLUE}[INFO]${NC} Creating venv and installing PyInstaller..."
uv venv --python 3.11
uv pip install pyinstaller

echo -e "${BLUE}[INFO]${NC} Locking and syncing dependencies..."
uv sync --python 3.11

echo -e "${BLUE}[INFO]${NC} Compiling with PyInstaller..."
uv run --python 3.11 pyinstaller main.py --name AXIOM --windowed --noconfirm --clean

# 2. AppDir Construction
echo -e "${BLUE}[INFO]${NC} Constructing AXIOM.AppDir..."
APPDIR="AXIOM.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

echo -e "${BLUE}[INFO]${NC} Copying binaries to AppDir..."
cp -r dist/AXIOM/* "$APPDIR/usr/bin/"

echo -e "${BLUE}[INFO]${NC} Generating axiom.desktop..."
cat <<EOF > "$APPDIR/axiom.desktop"
[Desktop Entry]
Name=AXIOM Pro
Exec=AXIOM
Icon=axiom-logo
Type=Application
Categories=Utility;Development;
EOF

echo -e "${BLUE}[INFO]${NC} Setting up icon..."
if [ -f "assets/axiom-logo.png" ]; then
    cp assets/axiom-logo.png "$APPDIR/"
else
    echo -e "${BLUE}[INFO]${NC} 'assets/axiom-logo.png' not found. Creating a default dummy icon..."
    # Generate a tiny 1x1 transparent PNG file as a fallback
    echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" | base64 -d > "$APPDIR/axiom-logo.png"
fi

echo -e "${BLUE}[INFO]${NC} Creating AppRun symlink..."
# AppRun must point to the executable relative to the AppDir root
cat <<EOF > "$APPDIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\${HERE}/usr/bin/AXIOM" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

# 3. AppImage Packaging
echo -e "${BLUE}[INFO]${NC} Checking for appimagetool..."
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    echo -e "${BLUE}[INFO]${NC} Downloading appimagetool..."
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

echo -e "${BLUE}[INFO]${NC} Packaging AppImage..."
# Run appimagetool
./appimagetool-x86_64.AppImage "$APPDIR"

echo -e "${BLUE}[INFO]${NC} Cleaning up temporary AppDir..."
rm -rf "$APPDIR"

echo -e "${GREEN}[SUCCESS]${NC} Build complete! Distributable AppImage has been generated."
