"""Tests for axiom.profile — AxiomProfile save/load/serialize."""

import json
import pytest
from pathlib import Path

from axiom.profile import (
    AxiomProfile,
    PersonalityConfig,
    BehaviorConfig,
    GuardrailConfig,
    EvolutionConfig,
    load_profile,
    save_profile,
    profile_exists,
)


class TestPersonalityConfig:
    def test_defaults(self):
        p = PersonalityConfig()
        assert p.vocabulary == 0.5
        assert p.humor == 0.5

    def test_clamps_above_one(self):
        p = PersonalityConfig(vocabulary=2.0, humor=3.0)
        assert p.vocabulary == 1.0
        assert p.humor == 1.0

    def test_clamps_below_zero(self):
        p = PersonalityConfig(vocabulary=-1.0)
        assert p.vocabulary == 0.0

    def test_accepts_string_numeric(self):
        p = PersonalityConfig(vocabulary="0.7")
        assert p.vocabulary == 0.7


class TestBehaviorConfig:
    def test_defaults(self):
        b = BehaviorConfig()
        assert b.autonomy == 0.5

    def test_clamps(self):
        b = BehaviorConfig(autonomy=5.0, risk_tolerance=-2.0)
        assert b.autonomy == 1.0
        assert b.risk_tolerance == 0.0


class TestAxiomProfile:
    def test_default_creation(self):
        profile = AxiomProfile()
        assert profile.genesis_version == 3
        assert profile.theme == "minimal"
        assert isinstance(profile.personality, PersonalityConfig)
        assert isinstance(profile.behavior, BehaviorConfig)

    def test_to_dict_roundtrip(self):
        profile = AxiomProfile(theme="dark")
        profile.workspace_paths = ["/tmp"]
        d = profile.to_dict()
        restored = AxiomProfile.from_dict(d)
        assert restored.theme == "dark"
        assert restored.workspace_paths == ["/tmp"]

    def test_to_json_roundtrip(self):
        profile = AxiomProfile(theme="minimal")
        j = profile.to_json()
        restored = AxiomProfile.from_json(j)
        assert restored.theme == "minimal"
        assert restored.genesis_version == 3

    def test_from_dict_ignores_unknown_fields(self):
        d = {"theme": "blue", "unknown_field": 42}
        profile = AxiomProfile.from_dict(d)
        assert profile.theme == "blue"

    def test_from_dict_empty(self):
        profile = AxiomProfile.from_dict({})
        assert profile.genesis_version == 3
        assert profile.theme == "minimal"

    def test_guardrails_preserved(self):
        profile = AxiomProfile()
        profile.guardrails.confidence_threshold = 0.9
        d = profile.to_dict()
        restored = AxiomProfile.from_dict(d)
        assert restored.guardrails.confidence_threshold == 0.9


class TestProfileFileOps:
    def test_save_and_load_roundtrip(self, tmp_path):
        profile = AxiomProfile(theme="test")
        p = tmp_path / "profile.json"
        save_profile(profile, p)
        loaded = load_profile(p)
        assert loaded.theme == "test"
        assert loaded.created != ""

    def test_load_missing_returns_defaults(self, tmp_path):
        loaded = load_profile(tmp_path / "nonexistent.json")
        assert loaded.theme == "minimal"
        assert loaded.genesis_version == 3

    def test_load_corrupt_returns_defaults(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json {{{")
        loaded = load_profile(p)
        assert loaded.theme == "minimal"

    def test_profile_exists_true(self, tmp_path):
        p = tmp_path / "exists.json"
        p.write_text("{}")
        assert profile_exists(p) is True

    def test_profile_exists_false(self, tmp_path):
        assert profile_exists(tmp_path / "nope.json") is False

    def test_save_sets_timestamps(self, tmp_path):
        profile = AxiomProfile()
        p = tmp_path / "profile.json"
        save_profile(profile, p)
        loaded = load_profile(p)
        assert loaded.created != ""
        assert loaded.evolution.last_calibrated != ""
