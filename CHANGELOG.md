# Changelog

## [v11.3.0] - Production Hardening & CI/CD
This release hardens the build system, wires in OTA capabilities, and eliminates UI teardown aborts for a pristine out-of-the-box experience.

### Added
- **Declarative Theme Engine:** Dynamic JSON-based theme registry loaded effortlessly into PySide6 `QSS` layouts without hardcoded hex colors.
- **OTA Updater:** Implemented GitHub Release polling in `axiom/network/updater.py` to prompt users when a newer `AppImage` tag drops.
- **OOBE Wizard:** Full Out-Of-Box Experience (`axiom/gui/widgets/oobe_wizard.py`) providing a guided setup for Local LLMs on first boot.
- **Automated CI/CD:** GitHub Actions `release.yml` now runs headless PySide6 test suites (`QT_QPA_PLATFORM=offscreen`) and automatically builds/attaches the AppImage for tagged releases.

### Fixed
- **Headless PySide6 Test Architecture:** Resolved fatal C++ `SIGABRT` crashes on PyInstaller teardown by systematically yielding and `quit()`ing `QThread` instances within `AxiomHubDialog`.
- **AppImage Build Resilience:** Fortified `scripts/build_appimage.sh` with correct `usr/share/applications` AppDir directory structure and explicit `set -e` failure trapping.
- **Circuit Breakers:** `SystemHealthWatchdog` now survives nested permission errors silently rather than stalling the central EventBus.

