#!/usr/bin/env bash
# Build an AppImage for the Phoniebox Installer.

set -e

APP="phoniebox-installer"
VERSION=$(python -c "import phoniebox_installer; print(phoniebox_installer.__version__)")

# Build with PyInstaller (onefile, windowed). On Linux the --add-data
# separator is ':'; the bundle layout must match get_resource_path().
pyinstaller --onefile --windowed \
    --name "$APP" \
    --add-data "phoniebox_installer/resources:phoniebox_installer/resources" \
    phoniebox_installer/main.py

# Prepare AppDir structure
APPDIR="AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons"

cp "dist/$APP" "$APPDIR/usr/bin/"
cp "packaging/linux/$APP.desktop" "$APPDIR/usr/share/applications/"
cp packaging/linux/AppRun "$APPDIR/"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/$APP"

# Download appimagetool if needed
if ! command -v appimagetool &>/dev/null; then
    wget -q -O appimagetool \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
    APPIMAGETOOL="./appimagetool"
else
    APPIMAGETOOL="appimagetool"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "Phoniebox-Installer-${VERSION}-x86_64.AppImage"
echo "AppImage created: Phoniebox-Installer-${VERSION}-x86_64.AppImage"
