"""Test suite for axiom.config (AxiomConfig, get_config, set_config)."""

from axiom.config import AxiomConfig, get_config, set_config


class TestAxiomConfigDefaults:
    def test_default_values(self):
        config = AxiomConfig()

        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.ollama_model == "qwen3:8b"
        assert config.db_path == "axiom.db"
        assert config.sandbox_mode is True


class TestAxiomConfigFromDict:
    def test_from_dict_applies_known_fields(self):
        config = AxiomConfig.from_dict({"debug": True, "ollama_model": "mistral"})

        assert config.debug is True
        assert config.ollama_model == "mistral"

    def test_from_dict_ignores_unknown_fields(self):
        config = AxiomConfig.from_dict({"debug": True, "not_a_real_field": 123})

        assert config.debug is True
        assert not hasattr(config, "not_a_real_field")

    def test_from_dict_with_empty_dict_uses_defaults(self):
        config = AxiomConfig.from_dict({})

        assert config == AxiomConfig()


class TestAxiomConfigToDict:
    def test_to_dict_round_trips_through_from_dict(self):
        original = AxiomConfig(debug=True, max_agents=5, sandbox_mode=False)

        restored = AxiomConfig.from_dict(original.to_dict())

        assert restored == original

    def test_to_dict_contains_all_expected_keys(self):
        config = AxiomConfig()

        data = config.to_dict()

        assert set(data.keys()) == {
            "debug",
            "log_level",
            "proactive_kernel",
            "ollama_base_url",
            "ollama_model",
            "embedding_model",
            "ollama_temperature",
            "db_path",
            "max_history",
            "max_agents",
            "max_tools",
            "event_history_limit",
            "sandbox_mode",
            "allow_system_tools",
            "allow_cloud_fallback",
            "monitor_window_focus",
            "monitor_clipboard",
        }


class TestGlobalConfig:
    def test_get_config_returns_an_axiom_config(self):
        assert isinstance(get_config(), AxiomConfig)

    def test_set_config_replaces_global_instance(self):
        original = get_config()
        try:
            new_config = AxiomConfig(debug=True)
            set_config(new_config)

            assert get_config() is new_config
            assert get_config().debug is True
        finally:
            set_config(original)

    def test_set_config_is_visible_globally(self):
        """Changes made via set_config are visible to any other get_config() caller."""
        original = get_config()
        try:
            set_config(AxiomConfig(log_level="DEBUG"))

            assert get_config().log_level == "DEBUG"
        finally:
            set_config(original)
