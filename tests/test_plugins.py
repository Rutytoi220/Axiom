"""Test suite for the AXIOM plugin system.

Covers BasePlugin's shared lifecycle behavior plus the two concrete plugins
(AutomationPlugin, NXBTPlugin) that the CLI registers on every startup. This
subsystem previously had zero test coverage despite being live, production
code exercised on every AXIOM run.
"""

from datetime import datetime

from axiom.plugins import AutomationPlugin, NXBTPlugin
from axiom.plugins.automation_plugin import AutomationTask


class TestBasePluginLifecycle:
    """Exercised via AutomationPlugin, which needs no external state."""

    def test_new_plugin_starts_disabled(self):
        plugin = AutomationPlugin()
        assert plugin.is_enabled() is False

    def test_enable_and_disable_toggle_state(self):
        plugin = AutomationPlugin()

        plugin.enable()
        assert plugin.is_enabled() is True

        plugin.disable()
        assert plugin.is_enabled() is False

    def test_get_info_reports_identity_and_state(self):
        plugin = AutomationPlugin()
        plugin.initialize({"key": "value"})
        plugin.enable()

        info = plugin.get_info()

        assert info == {
            "plugin_id": "automation",
            "name": "Automation Plugin",
            "version": "1.0.0",
            "enabled": True,
            "config": {"key": "value"},
        }


class TestAutomationPlugin:
    def test_initialize_sets_config_and_returns_true(self):
        plugin = AutomationPlugin()

        assert plugin.initialize({"interval": 60}) is True
        assert plugin.config == {"interval": 60}

    def test_initialize_without_config_defaults_to_empty_dict(self):
        plugin = AutomationPlugin()

        assert plugin.initialize() is True
        assert plugin.config == {}

    def test_register_and_list_tasks(self):
        plugin = AutomationPlugin()
        task = AutomationTask(task_id="t1", name="Test Task", trigger="event", action=lambda: None)

        assert plugin.register_task(task) is True
        tasks = plugin.list_tasks()

        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "t1"
        assert tasks[0]["enabled"] is True

    def test_unregister_task_removes_it(self):
        plugin = AutomationPlugin()
        task = AutomationTask(task_id="t1", name="Test Task", trigger="event", action=lambda: None)
        plugin.register_task(task)

        assert plugin.unregister_task("t1") is True
        assert plugin.list_tasks() == []

    def test_unregister_missing_task_returns_false(self):
        plugin = AutomationPlugin()

        assert plugin.unregister_task("does_not_exist") is False

    def test_enable_and_disable_missing_task_returns_false(self):
        plugin = AutomationPlugin()

        assert plugin.enable_task("does_not_exist") is False
        assert plugin.disable_task("does_not_exist") is False

    def test_disable_task_prevents_execution(self):
        plugin = AutomationPlugin()
        calls = []
        task = AutomationTask(task_id="t1", name="T", trigger="event", action=lambda: calls.append(1))
        plugin.register_task(task)

        plugin.disable_task("t1")
        result = plugin.execute_task("t1")

        assert result is False
        assert calls == []

    def test_enable_task_allows_execution_again(self):
        plugin = AutomationPlugin()
        calls = []
        task = AutomationTask(task_id="t1", name="T", trigger="event", action=lambda: calls.append(1))
        plugin.register_task(task)
        plugin.disable_task("t1")

        plugin.enable_task("t1")
        result = plugin.execute_task("t1")

        assert result is True
        assert calls == [1]

    def test_execute_missing_task_returns_false(self):
        plugin = AutomationPlugin()

        assert plugin.execute_task("does_not_exist") is False

    def test_execute_task_calls_action(self):
        plugin = AutomationPlugin()
        calls = []
        task = AutomationTask(task_id="t1", name="T", trigger="event", action=lambda: calls.append("ran"))
        plugin.register_task(task)

        assert plugin.execute_task("t1") is True
        assert calls == ["ran"]

    def test_execute_task_action_exception_is_caught(self):
        plugin = AutomationPlugin()

        def boom():
            raise RuntimeError("action failed")

        task = AutomationTask(task_id="t1", name="T", trigger="event", action=boom)
        plugin.register_task(task)

        assert plugin.execute_task("t1") is False

    def test_get_task_info_for_missing_task_returns_none(self):
        plugin = AutomationPlugin()

        assert plugin.get_task_info("does_not_exist") is None

    def test_get_task_info_returns_task_details(self):
        plugin = AutomationPlugin()
        task = AutomationTask(task_id="t1", name="Backup", trigger="time", action=lambda: None)
        plugin.register_task(task)

        info = plugin.get_task_info("t1")

        assert info["task_id"] == "t1"
        assert info["name"] == "Backup"
        assert info["trigger"] == "time"
        assert info["enabled"] is True

    def test_automation_task_defaults_created_at(self):
        task = AutomationTask(task_id="t1", name="T", trigger="event", action=lambda: None)

        assert isinstance(task.created_at, datetime)

    def test_shutdown_clears_tasks(self):
        plugin = AutomationPlugin()
        plugin.register_task(
            AutomationTask(task_id="t1", name="T", trigger="event", action=lambda: None)
        )

        assert plugin.shutdown() is True
        assert plugin.list_tasks() == []


class TestNXBTPlugin:
    def test_initialize_sets_up_mock_controller(self):
        plugin = NXBTPlugin()

        assert plugin.initialize() is True
        assert plugin.is_connected() is False

    def test_actions_fail_before_connecting(self):
        plugin = NXBTPlugin()
        plugin.initialize()

        assert plugin.press_button("A") is False
        assert plugin.release_button("A") is False
        assert plugin.move_stick("left", 0.5, 0.5) is False

    def test_connect_requires_initialize_first(self):
        plugin = NXBTPlugin()

        # Controller is None until initialize() runs _setup_mock_controller.
        assert plugin.connect() is False

    def test_connect_and_disconnect_toggle_state(self):
        plugin = NXBTPlugin()
        plugin.initialize()

        assert plugin.connect() is True
        assert plugin.is_connected() is True

        assert plugin.disconnect() is True
        assert plugin.is_connected() is False

    def test_press_and_release_button_after_connecting(self):
        plugin = NXBTPlugin()
        plugin.initialize()
        plugin.connect()

        assert plugin.press_button("A") is True
        assert plugin._controller["buttons"]["A"] is True

        assert plugin.release_button("A") is True
        assert plugin._controller["buttons"]["A"] is False

    def test_move_stick_after_connecting(self):
        plugin = NXBTPlugin()
        plugin.initialize()
        plugin.connect()

        assert plugin.move_stick("left", 0.25, -0.5) is True
        assert plugin._controller["sticks"]["left"] == {"x": 0.25, "y": -0.5}

    def test_shutdown_disconnects_when_connected(self):
        plugin = NXBTPlugin()
        plugin.initialize()
        plugin.connect()

        assert plugin.shutdown() is True
        assert plugin.is_connected() is False

    def test_shutdown_when_never_connected_succeeds(self):
        plugin = NXBTPlugin()
        plugin.initialize()

        assert plugin.shutdown() is True

class TestDynamicPluginManager:
    def test_dynamic_plugin_loading(self, mock_home_directory):
        from axiom.core.plugin_manager import PluginManager
        from pathlib import Path
        
        plugins_dir = Path(mock_home_directory) / ".config" / "ChienGPT" / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        
        # Write a valid plugin
        valid_plugin = plugins_dir / "valid_tool.py"
        valid_plugin.write_text("""
from axiom.tools.base import BaseTool

class TestPluginTool(BaseTool):
    def __init__(self):
        super().__init__('test_plugin', 'Test Plugin', 'Test description')
    
    async def execute(self, **kw):
        pass
""")

        # Write a malformed plugin
        invalid_plugin = plugins_dir / "invalid_tool.py"
        invalid_plugin.write_text("""
from axiom.tools.base import BaseTool

class BrokenPluginTool(BaseTool):
    def __init__(self):
        super().__init__('broken', 'Broken', 'broken')
    
    syntax error!
""")

        pm = PluginManager()
        tools = pm.load_user_tools()
        
        # We should only get the valid tool, and the program should not crash
        assert len(tools) == 1
        assert tools[0].tool_id == "test_plugin"
