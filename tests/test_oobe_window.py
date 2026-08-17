"""Tests for the AXIOM V11 "First Contact" OOBE wizard.

Covers page navigation, the diagnostics/model-list background workers, the
finish/save handoff, the Escape-key safety guard, and the ``oobe_completed``
config migration path for existing installs.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Guard: skip ALL tests if PySide6 isn't installed so the test suite
# doesn't fail on headless CI machines without Qt.
pytest.importorskip("PySide6", reason="PySide6 not installed — skipping GUI tests")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog  # noqa: E402

from axiom.config import AxiomConfig, get_config, set_config  # noqa: E402
from axiom.gui.windows.onboarding import (  # noqa: E402
    OOBEWindow,
    _DiagnosticsWorker,
    _ModelListWorker,
    _guess_vision_model,
)


@pytest.fixture
def isolated_config():
    """Save/restore the global AxiomConfig so this test's mutations never
    leak into other tests in the session (mirrors tests/test_config.py)."""
    original = get_config()
    try:
        set_config(AxiomConfig())
        yield get_config()
    finally:
        set_config(original)


@pytest.fixture
def oobe_window(qtbot, isolated_config, monkeypatch):
    # Page/navigation/finish tests below drive diagnostics/model state via
    # direct calls (apply_result / populate_models), so the real background
    # workers are disabled here to avoid a race between their real network
    # probes and the test's own assertions/manual updates. The workers
    # themselves are still fully exercised by TestDiagnosticsWorker and
    # TestModelListWorker below.
    monkeypatch.setattr(OOBEWindow, "_start_background_scans", lambda self: None)

    win = OOBEWindow()
    qtbot.addWidget(win)
    yield win
    for worker in (win._diag_worker, win._model_worker):
        if worker is not None and worker.isRunning():
            worker.wait(2000)


class TestOOBEWindowInitialState:
    def test_has_four_pages(self, oobe_window):
        assert oobe_window.stack.count() == 4

    def test_starts_on_welcome_page(self, oobe_window):
        assert oobe_window.stack.currentIndex() == 0

    def test_back_button_disabled_on_first_page(self, oobe_window):
        assert oobe_window.back_btn.isEnabled() is False

    def test_next_button_says_next_on_first_page(self, oobe_window):
        assert oobe_window.next_btn.text() == "Next"

    def test_is_frameless_dialog(self, oobe_window):
        assert isinstance(oobe_window, QDialog)
        assert bool(oobe_window.windowFlags() & Qt.WindowType.FramelessWindowHint)


class TestOOBEWindowNavigation:
    def test_next_advances_page(self, oobe_window):
        oobe_window._go_next()
        assert oobe_window.stack.currentIndex() == 1
        assert oobe_window.back_btn.isEnabled() is True

    def test_back_disabled_only_on_first_page(self, oobe_window):
        oobe_window._go_next()
        oobe_window._go_back()
        assert oobe_window.stack.currentIndex() == 0
        assert oobe_window.back_btn.isEnabled() is False

    def test_next_becomes_finish_on_last_page(self, oobe_window):
        for _ in range(3):
            oobe_window._go_next()
        assert oobe_window.stack.currentIndex() == 3
        assert oobe_window.next_btn.text() == "Finish"

    def test_finish_reverts_to_next_when_going_back(self, oobe_window):
        for _ in range(3):
            oobe_window._go_next()
        oobe_window._go_back()
        assert oobe_window.next_btn.text() == "Next"

    def test_back_is_noop_on_first_page(self, oobe_window):
        oobe_window._go_back()
        assert oobe_window.stack.currentIndex() == 0


class TestOOBEWindowDiagnosticsPage:
    def test_rows_start_in_scanning_state(self, oobe_window):
        for row in oobe_window.diagnostics_page.rows.values():
            assert row.status_label.text() == "⏳"

    def test_apply_result_ok_shows_checkmark(self, oobe_window):
        oobe_window.diagnostics_page.apply_result("ollama", True, "Running")
        row = oobe_window.diagnostics_page.rows["ollama"]
        assert row.status_label.text() == "✅"
        assert row.detail_label.text() == "Running"

    def test_apply_result_failure_shows_warning(self, oobe_window):
        oobe_window.diagnostics_page.apply_result("tailscale", False, "Not connected")
        row = oobe_window.diagnostics_page.rows["tailscale"]
        assert row.status_label.text() == "⚠️"
        assert row.detail_label.text() == "Not connected"

    def test_apply_result_unknown_check_id_is_ignored(self, oobe_window):
        # Must not raise even if an unexpected check_id arrives.
        oobe_window.diagnostics_page.apply_result("unknown_check", True, "n/a")


class TestOOBEWindowModelPage:
    def test_populate_with_models_enables_combos(self, oobe_window):
        oobe_window.model_page.populate_models(["llama3:8b", "llava:7b"])
        assert oobe_window.model_page.chat_combo.isEnabled() is True
        assert oobe_window.model_page.vision_combo.isEnabled() is True
        assert oobe_window.model_page.chat_combo.count() == 2

    def test_populate_preselects_current_chat_model(self, oobe_window, isolated_config):
        isolated_config.ollama_model = "llava:7b"
        oobe_window.model_page.populate_models(["llama3:8b", "llava:7b"])
        assert oobe_window.model_page.selected_chat_model() == "llava:7b"

    def test_populate_preselects_vision_model_heuristic(self, oobe_window):
        oobe_window.model_page.populate_models(["llama3:8b", "llava:7b"])
        assert oobe_window.model_page.selected_vision_model() == "llava:7b"

    def test_populate_with_empty_list_disables_combos(self, oobe_window):
        oobe_window.model_page.populate_models([])
        assert oobe_window.model_page.chat_combo.isEnabled() is False
        assert oobe_window.model_page.vision_combo.isEnabled() is False
        assert oobe_window.model_page.selected_chat_model() == ""
        assert oobe_window.model_page.selected_vision_model() == ""
        assert "No installed models found" in oobe_window.model_page.status_label.text()


class TestGuessVisionModel:
    def test_finds_llava(self):
        assert _guess_vision_model(["llama3:8b", "llava:7b"]) == "llava:7b"

    def test_finds_minicpm_v(self):
        assert _guess_vision_model(["mistral:7b", "minicpm-v:8b"]) == "minicpm-v:8b"

    def test_returns_none_when_no_match(self):
        assert _guess_vision_model(["llama3:8b", "mistral:7b"]) is None

    def test_empty_list_returns_none(self):
        assert _guess_vision_model([]) is None


class TestOOBEWindowFinish:
    def test_finish_marks_oobe_completed_and_saves_models(self, qtbot, oobe_window, isolated_config):
        # NOTE: the session-wide `mock_home_directory` fixture (tests/conftest.py)
        # already redirects Path.home() to a temp dir, so config.save() here
        # never touches the real ~/.config/axiom/settings.json.
        oobe_window.model_page.populate_models(["llama3:8b", "llava:7b"])
        oobe_window.model_page.chat_combo.setCurrentText("llama3:8b")
        oobe_window.model_page.vision_combo.setCurrentText("llava:7b")

        with qtbot.waitSignal(oobe_window.initialization_complete, timeout=3000):
            oobe_window._on_finish()

        assert isolated_config.oobe_completed is True
        assert isolated_config.first_launch is False
        assert isolated_config.ollama_model == "llama3:8b"
        assert isolated_config.vision_model == "llava:7b"
        assert oobe_window.result() == QDialog.DialogCode.Accepted

    def test_finish_disables_nav_buttons_immediately(self, oobe_window):
        oobe_window.model_page.populate_models([])
        oobe_window._on_finish()
        assert oobe_window.next_btn.isEnabled() is False
        assert oobe_window.back_btn.isEnabled() is False


class TestOOBEWindowSafetyGuards:
    def test_escape_key_does_not_close_dialog(self, qtbot, oobe_window):
        oobe_window.show()
        qtbot.keyClick(oobe_window, Qt.Key.Key_Escape)
        assert oobe_window.isVisible() is True
        assert oobe_window.result() == QDialog.DialogCode.Rejected  # never triggered


class TestDiagnosticsWorker:
    def test_emits_all_three_checks(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            "axiom.llm.ollama_client.OllamaClient.is_available", lambda self: True
        )
        monkeypatch.setattr(
            "axiom.gui.windows.onboarding.subprocess.run",
            lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
        )
        # Force the psutil interface-scan fallback to find nothing too, so
        # this assertion is deterministic regardless of the host's own
        # network setup (some dev/CI machines may have a real 100.x.x.x
        # Tailscale interface, which would otherwise make "tailscale" look
        # connected here).
        monkeypatch.setattr("psutil.net_if_addrs", lambda: {"lo": []})
        monkeypatch.setattr(
            "axiom.core.audio.AudioManager.instance",
            staticmethod(lambda: type("Fake", (), {"has_tts": True, "has_stt": False})()),
        )

        worker = _DiagnosticsWorker()
        received: list[tuple[str, bool, str]] = []
        worker.check_finished.connect(lambda cid, ok, detail: received.append((cid, ok, detail)))

        worker.start()
        qtbot.waitUntil(lambda: len(received) == 3, timeout=8000)
        worker.wait(2000)

        ids = {r[0] for r in received}
        assert ids == {"ollama", "tailscale", "audio"}
        results = dict((cid, (ok, detail)) for cid, ok, detail in received)
        assert results["ollama"][0] is True
        assert results["tailscale"][0] is False
        assert results["audio"] == (True, "TTS ready (STT unavailable)")


class TestModelListWorker:
    def test_emits_models_from_client(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            "axiom.llm.ollama_client.OllamaClient.list_models",
            lambda self: ["llama3:8b", "llava:7b"],
        )
        worker = _ModelListWorker()
        received: list[list[str]] = []
        worker.models_ready.connect(received.append)

        worker.start()
        qtbot.waitUntil(lambda: len(received) == 1, timeout=8000)
        worker.wait(2000)

        assert received[0] == ["llama3:8b", "llava:7b"]

    def test_emits_empty_list_on_failure(self, qtbot, monkeypatch):
        def _raise(self):
            raise ConnectionError("boom")

        monkeypatch.setattr("axiom.llm.ollama_client.OllamaClient.list_models", _raise)
        worker = _ModelListWorker()
        received: list[list[str]] = []
        worker.models_ready.connect(received.append)

        worker.start()
        qtbot.waitUntil(lambda: len(received) == 1, timeout=8000)
        worker.wait(2000)

        assert received[0] == []


class TestOobeCompletedMigration:
    """Backward-compat: existing users who already ran the old OOBE (i.e. have
    a legacy ui_config.json) should not be forced through the new wizard."""

    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_brand_new_install_defaults_to_false(self, tmp_path):
        with patch("axiom.config.CONFIG_DIR", tmp_path / ".config" / "axiom"):
            assert AxiomConfig.load().oobe_completed is False

    def test_legacy_ui_config_migrates_to_true(self, tmp_path):
        config_dir = tmp_path / ".config" / "axiom"
        self._write_json(config_dir / "ui_config.json", {"theme": "dark"})
        self._write_json(config_dir / "settings.json", {"ollama_model": "llama3:8b"})

        with patch("axiom.config.CONFIG_DIR", tmp_path / ".config" / "axiom"):
            cfg = AxiomConfig.load()
            assert cfg.oobe_completed is True
            assert cfg.ollama_model == "llama3:8b"

    def test_explicit_false_is_respected_even_with_legacy_ui_config(self, tmp_path):
        config_dir = tmp_path / ".config" / "axiom"
        self._write_json(config_dir / "ui_config.json", {"theme": "dark"})
        self._write_json(config_dir / "settings.json", {"oobe_completed": False})

        with patch("axiom.config.CONFIG_DIR", tmp_path / ".config" / "axiom"):
            assert AxiomConfig.load().oobe_completed is False

    def test_explicit_true_is_respected(self, tmp_path):
        config_dir = tmp_path / ".config" / "axiom"
        self._write_json(config_dir / "settings.json", {"oobe_completed": True})

        with patch("axiom.config.CONFIG_DIR", tmp_path / ".config" / "axiom"):
            assert AxiomConfig.load().oobe_completed is True
