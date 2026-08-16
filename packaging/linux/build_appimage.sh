#!/usr/bin/env bash
# Build an AppImage for the Phoniebox Installer.

set -e

# Use the project venv if present and not already active, so that
# `python` and `pyinstaller` resolve to the local environment.
if [[ -z "${VIRTUAL_ENV:-}" && -d ".venv/bin" ]]; then
    export VIRTUAL_ENV="$(pwd)/.venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi

if ! command -v pyinstaller &>/dev/null; then
    echo "ERROR: pyinstaller not found."
    echo "Install the dev dependencies first:"
    echo "  uv pip install --python .venv/bin/python -r requirements-dev.txt"
    exit 1
fi

APP="phoniebox-installer"
VERSION=$(python -c "import phoniebox_installer; print(phoniebox_installer.__version__)")

# The stylesheet no longer uses icon files, but the desktop entry and the
# welcome page logo rely on phoniebox_logo.png. Fail early if it is missing.
if [[ ! -f "phoniebox_installer/resources/icons/phoniebox_logo.png" ]]; then
    echo "ERROR: missing resource phoniebox_installer/resources/icons/phoniebox_logo.png" >&2
    echo "       The AppImage would ship without the application logo." >&2
    exit 1
fi

# Build with PyInstaller. Use --onedir (not --onefile): the AppImage squashfs
# already compresses the payload, and a onefile archive inside would only bloat
# it and defeat that compression. On Linux the --add-data separator is ':'; the
# bundle layout must match get_resource_path().
pyinstaller --onedir --windowed --strip --noconfirm \
    --name "$APP" \
    --add-data "phoniebox_installer/resources:phoniebox_installer/resources" \
    --exclude-module tkinter \
    --exclude-module matplotlib \
    --exclude-module numpy \
    --exclude-module pandas \
    --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtWebEngineWidgets \
    phoniebox_installer/main.py

# ---------------------------------------------------------------------------
# Shrink the bundle by removing Qt components a plain QtWidgets app does not
# need. PyInstaller's Qt hook collects every plugin together with its
# transitive system-library dependencies, which pulls in the GTK3 platform
# theme (-> GTK3 + a second copy of ICU), QtQml/Quick/Pdf/Network and ~80 MB
# of unused libraries. Verified via DT_NEEDED reverse-dependency analysis.
# ---------------------------------------------------------------------------
prune_bundle() {
    local internal_dir="$1"
    (
        cd "$internal_dir" || exit 1

        # Qt plugins that drag in unused Qt modules / system libraries.
        rm -rf PySide6/Qt/plugins/platformthemes         # libqgtk3 -> GTK3 + system ICU
        rm -rf PySide6/Qt/plugins/networkinformation     # -> QtNetwork
        rm -rf PySide6/Qt/plugins/tls                    # -> QtNetwork + OpenSSL
        rm -rf PySide6/Qt/plugins/generic                # evdev/tslib input
        rm -rf PySide6/Qt/plugins/egldeviceintegrations  # -> QtEglFS
        rm -f  PySide6/Qt/plugins/imageformats/libqpdf.so
        rm -f  PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so

        # Orphaned Qt shared libraries (only referenced by the plugins above).
        rm -f PySide6/Qt/lib/libQt6Network.so.6
        rm -f PySide6/Qt/lib/libQt6Pdf.so.6
        rm -f PySide6/Qt/lib/libQt6Qml.so.6
        rm -f PySide6/Qt/lib/libQt6QmlMeta.so.6
        rm -f PySide6/Qt/lib/libQt6QmlModels.so.6
        rm -f PySide6/Qt/lib/libQt6QmlWorkerScript.so.6
        rm -f PySide6/Qt/lib/libQt6Quick.so.6
        rm -f PySide6/Qt/lib/libQt6VirtualKeyboard.so.6
        rm -f PySide6/Qt/lib/libQt6VirtualKeyboardQml.so.6
        rm -f PySide6/Qt/lib/libQt6EglFSDeviceIntegration.so.6
        rm -f PySide6/Qt/lib/libQt6EglFsKmsSupport.so.6

        # System libraries only needed by the GTK3 platform theme.
        rm -f libgtk-3.so.0 libgdk-3.so.0 libgdk_pixbuf-2.0.so.0
        rm -f libcairo.so.2 libcairo-gobject.so.2 libcairo-script-interpreter.so.2
        rm -f libpango-1.0.so.0 libpangocairo-1.0.so.0 libpangoft2-1.0.so.0
        rm -f libharfbuzz.so.0 libharfbuzz-subset.so.0 libharfbuzz-gobject.so.0
        rm -f libgraphite2.so.3 libfribidi.so.0 libdatrie.so.1 libthai.so.0
        rm -f libepoxy.so.0 libpixman-1.so.0 libglycin-2.so.0 libglycin-gtk4-2.so.0
        rm -f libicudata.so.78 libicuuc.so.78 libicui18n.so.78
        rm -f libgio-2.0.so.0

        # Remaining GLib/GTK-ecosystem orphans (not linked by QtGui/QtWidgets).
        rm -f libatk-1.0.so.0 libatk-bridge-2.0.so.0 libatspi.so.0
        rm -f libblkid.so.1 libmount.so.1 libcloudproviders.so.0
        rm -f libcom_err.so.2 libgssapi_krb5.so.2 libk5crypto.so.3 libkeyutils.so.1
        rm -f libkrb5.so.3 libkrb5support.so.0
        rm -f libgmodule-2.0.so.0 libgobject-2.0.so.0 libjson-glib-1.0.so.0
        rm -f liblcms2.so.2 libseccomp.so.2
        rm -f libsqlite3.so.0 libtinysparql-3.0.so.0 libxml2.so.16

        # Qt translations: the UI is English-only and uses no QTranslator.
        rm -rf PySide6/Qt/translations
    )
}

prune_bundle "dist/$APP/_internal"

# Smoke-test the pruned bundle offscreen: it must start and enter the event
# loop. A missing required library would crash it immediately.
echo "Smoke-testing bundle (offscreen)..."
set +e
QT_QPA_PLATFORM=offscreen timeout 5 "dist/$APP/$APP" >/dev/null 2>&1
smoke_code=$?
set -e
if [ "$smoke_code" -eq 124 ]; then
    echo "Smoke test OK (app entered the event loop)."
elif [ "$smoke_code" -eq 0 ]; then
    echo "ERROR: bundle exited immediately (exit 0)." >&2
    exit 1
else
    echo "ERROR: bundle failed to start (exit $smoke_code)." >&2
    exit 1
fi

# Prepare AppDir structure
APPDIR="AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons"

cp -r "dist/$APP/"* "$APPDIR/usr/bin/"
# appimagetool looks for the .desktop file at the AppDir root.
cp "packaging/linux/$APP.desktop" "$APPDIR/"
cp "packaging/linux/$APP.desktop" "$APPDIR/usr/share/applications/"
# Icon referenced by the desktop file's Icon= field.
cp "phoniebox_installer/resources/icons/phoniebox_logo.png" "$APPDIR/$APP.png"
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

OUT="Phoniebox-Installer-${VERSION}-x86_64.AppImage"

# Build to a temporary name and atomically rename it into place. appimagetool
# refuses to overwrite a *running* AppImage ("Text file busy"), which would
# otherwise abort the build here and silently leave an old/stale AppImage on
# disk. `mv -f` replaces the directory entry even when an old instance is
# still executing, so a rebuild always wins.
ARCH=x86_64 "$APPIMAGETOOL" --comp xz "$APPDIR" "${OUT}.tmp"
mv -f "${OUT}.tmp" "$OUT"
echo "AppImage created: $OUT"

# The AppImage is the only deliverable: it embeds usr/bin/phoniebox-installer
# *and* usr/bin/_internal/ inside its SquashFS. Remove the intermediate
# PyInstaller output (dist/ build/) and the assembled AppDir so that the tree
# does not misleadingly suggest the result is an unpacked (non-self-contained)
# bundle next to the AppImage.
rm -rf dist build "$APPDIR"
echo "Done. Self-contained artifact: Phoniebox-Installer-${VERSION}-x86_64.AppImage"
