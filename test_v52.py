import sys, os
sys.path.insert(0, os.getcwd())

# 1. PackageEngine instantiation
from axiom.build.package_engine import PackageEngine
engine = PackageEngine()
assert "freeze" in engine.VALID_TARGETS
assert "deb" in engine.VALID_TARGETS
assert "rpm" in engine.VALID_TARGETS
assert "appimage" in engine.VALID_TARGETS
assert "exe" in engine.VALID_TARGETS
assert "dmg" in engine.VALID_TARGETS
assert "all" in engine.VALID_TARGETS
print("PackageEngine Test Passed")

# 2. freeze.py import and hidden-imports list
from axiom.build.freeze import HIDDEN_IMPORTS, build_hidden_import_args
args = build_hidden_import_args()
assert "--hidden-import" in args
assert "axiom" in HIDDEN_IMPORTS
print("Freeze Config Test Passed")

# 3. build_linux nfpm yaml generation
from axiom.build.build_linux import generate_nfpm_yaml
yaml = generate_nfpm_yaml("deb")
assert "axiom-daemon" in yaml
assert "/usr/bin/axiom-daemon" in yaml
assert "/usr/share/applications/axiom.desktop" in yaml
assert "/usr/lib/systemd/user/axiom.service" in yaml
assert "post_install.sh" in yaml
print("Linux Packaging Test Passed")

# 4. build_win Inno Setup generation
from axiom.build.build_win import generate_inno_setup_script
iss = generate_inno_setup_script()
assert "axiom-daemon.exe" in iss
assert "axiom-gui.exe" in iss
assert "5.2.0" in iss
print("Windows Packaging Test Passed")

# 5. build_mac plist generation
from axiom.build.build_mac import _generate_info_plist, _generate_launchd_plist
plist = _generate_info_plist()
assert "com.axiom.gui" in plist
assert "5.2.0" in plist
launchd = _generate_launchd_plist()
assert "com.axiom.daemon" in launchd
print("macOS Packaging Test Passed")

# 6. CLI do_package exists
from axiom.api.cli import CLI
assert hasattr(CLI, "do_package")
print("CLI Package Command Test Passed")
