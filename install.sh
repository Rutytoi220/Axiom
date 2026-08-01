#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  AXIOM Desktop v6.7 — Native Linux Installer
#  Installs the systemd background daemon and GNOME/KDE launcher
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[  OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[FAIL]${NC}  $*"; }

# ── Paths ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${SCRIPT_DIR}/deploy"

SYSTEMD_DIR="${HOME}/.config/systemd/user"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

SERVICE_SRC="${DEPLOY_DIR}/axiomd.service"
DESKTOP_SRC="${DEPLOY_DIR}/Axiom.desktop"
ICON_SRC="${SCRIPT_DIR}/axiom/gui/assets/logo.png"

# ── Banner ──────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║          AXIOM Desktop v6.7 — Linux Installer         ║"
echo "  ║       Local-First AI Orchestration for Linux          ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Preflight Checks ───────────────────────────────────────────
info "Running preflight checks..."

if ! command -v systemctl &>/dev/null; then
    error "systemctl not found. This installer requires systemd."
    exit 1
fi
success "systemd detected."

if ! command -v axiom &>/dev/null; then
    warn "'axiom' command not found in PATH."
    warn "Make sure the package is installed (pip install -e .) before enabling the service."
fi

if ! command -v axiom-gui &>/dev/null; then
    warn "'axiom-gui' command not found in PATH."
    warn "Install with: pip install -e '.[gui]'"
fi

# ── Step 1: Systemd User Service ───────────────────────────────
echo ""
info "Step 1/3: Installing systemd user service..."

if [ ! -f "${SERVICE_SRC}" ]; then
    error "Service file not found at ${SERVICE_SRC}"
    exit 1
fi

mkdir -p "${SYSTEMD_DIR}"
cp "${SERVICE_SRC}" "${SYSTEMD_DIR}/axiomd.service"
success "Copied axiomd.service → ${SYSTEMD_DIR}/"

systemctl --user daemon-reload
success "systemd user daemon reloaded."

systemctl --user enable axiomd.service 2>/dev/null || true
success "axiomd.service enabled on login."

systemctl --user start axiomd.service 2>/dev/null && \
    success "axiomd.service started." || \
    warn "Could not start axiomd.service now (will start on next login)."

# ── Step 2: Desktop Entry ──────────────────────────────────────
echo ""
info "Step 2/3: Installing desktop entry..."

if [ ! -f "${DESKTOP_SRC}" ]; then
    error "Desktop file not found at ${DESKTOP_SRC}"
    exit 1
fi

mkdir -p "${DESKTOP_DIR}"
cp "${DESKTOP_SRC}" "${DESKTOP_DIR}/Axiom.desktop"
success "Copied Axiom.desktop → ${DESKTOP_DIR}/"

# ── Step 3: Application Icon ──────────────────────────────────
echo ""
info "Step 3/3: Installing application icon..."

if [ -f "${ICON_SRC}" ]; then
    mkdir -p "${ICON_DIR}"
    cp "${ICON_SRC}" "${ICON_DIR}/axiom.png"
    success "Installed icon → ${ICON_DIR}/axiom.png"
else
    warn "Icon not found at ${ICON_SRC}. The launcher will use a generic icon."
fi

# ── Update Desktop Database ───────────────────────────────────
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
    success "Desktop database updated."
fi

if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    success "Icon cache updated."
fi

# ── Summary ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║            Installation Complete!                     ║"
echo "  ╠═══════════════════════════════════════════════════════╣"
echo "  ║  Daemon:   systemctl --user status axiomd            ║"
echo "  ║  Logs:     journalctl --user -u axiomd -f            ║"
echo "  ║  GUI:      Search 'AXIOM' in your app launcher       ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"
