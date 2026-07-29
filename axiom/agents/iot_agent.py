"""Physical World Agent.

A specialized agent equipped with IoTActuatorTool, designed to interpret
natural language intents (e.g., "dim the lights") into physical MQTT payloads.
"""
import logging
from axiom.agents.base_agent import SimpleBaseAgent
from axiom.tools.iot_mqtt import IoTActuatorTool

logger = logging.getLogger(__name__)

class PhysicalWorldAgent(SimpleBaseAgent):
    """Translates intents into physical environmental state changes."""
    
    def __init__(self, broker_host: str = "localhost"):
        super().__init__(name="PhysicalWorldAgent", role="IoT Actuation")
        self.iot_tool = IoTActuatorTool(broker_host=broker_host)
        
    def _system_prompt(self) -> str:
        return (
            "You are the PhysicalWorldAgent. Your job is to translate user intents into "
            "actions in the physical environment using the iot_actuate tool.\n"
            "If a user says 'dim the lights', map it to the correct MQTT topic (e.g., 'home/lights/set') "
            "with a valid payload (e.g., '{\"state\": \"ON\", \"brightness\": 128}').\n"
            "If they say 'I'm starting to code', prepare the environment by adjusting lighting or fans."
        )

    def execute_intent(self, intent: str) -> str:
        """Process an intent to actuate physical devices."""
        logger.info(f"PhysicalWorldAgent processing intent: '{intent}'")
        
        # In a full run, we would loop with the LLM. We mock the execution here for the demo.
        if "code" in intent.lower() or "dim" in intent.lower():
            # Mock LLM calling the tool
            result = self.iot_tool.execute({"topic": "home/office/light/set", "payload": "{\"brightness\": 100}"})
            if result.success:
                return "I've dimmed the lights to prepare your coding environment."
            else:
                return f"Failed to adjust environment: {result.error}"
                
        return "I'm not sure how to actuate the environment for that intent."
