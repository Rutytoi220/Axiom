import json
import logging
from axiom.tools.plugin_loader import axiom_tool

logger = logging.getLogger("axiom.tools.ui_plugins")

@axiom_tool(
    name="generate_interactive_widget",
    description="Generates and injects a dynamic, interactive HTML/JS widget into the user's chat window for visualizations, interactive calculations, or simulations.",
    parameters={
        "type": "object",
        "properties": {
            "widget_type": {
                "type": "string",
                "description": "The type of widget to generate. Examples: 'chart', 'calculator', 'physics_sim', 'markdown'."
            },
            "spec": {
                "type": "object",
                "description": "A JSON object defining the data and configuration for the widget. For a chart, this could include 'labels' and 'datasets'."
            }
        },
        "required": ["widget_type", "spec"]
    }
)
def generate_interactive_widget(widget_type: str, spec: dict) -> str:
    """Emits an event to generate a dynamic widget in the UI."""
    try:
        from axiom.services.governor import GovernorService
        gov = GovernorService.instance()
        if gov.event_bus:
            from axiom.core.events import Event
            event = Event(
                event_type="ui.widget_generated",
                source="generate_interactive_widget",
                data={
                    "widget_type": widget_type,
                    "spec": spec
                }
            )
            gov.event_bus.publish(event)
            return "SUCCESS: Widget specification sent to the UI. The user will see the interactive component."
        else:
            return "ERROR: EventBus not accessible. Cannot send widget to UI."
    except Exception as e:
        logger.error(f"Failed to emit widget event: {e}")
        return f"ERROR: Failed to generate widget - {e}"
