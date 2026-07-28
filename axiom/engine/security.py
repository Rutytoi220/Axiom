import re
import subprocess
import logging
from typing import Dict, Any, Tuple
from axiom.engine.audit_ledger import AuditLedger

logger = logging.getLogger(__name__)

class SecuritySandbox:
    """Security sandbox for evaluating and auditing tool executions."""
    
    HIGH_RISK_PATTERNS = [
        r'rm\s+-rf',
        r'sudo\s+',
        r'mkfs',
        r'dd\s+if=',
        r'/etc/',
        r'wget\s+',
        r'curl\s+',
    ]

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecuritySandbox, cls).__new__(cls)
            cls._instance.ledger = AuditLedger()
            cls._instance._compiled_patterns = [re.compile(p) for p in cls.HIGH_RISK_PATTERNS]
        return cls._instance

    def evaluate_command(self, agent_name: str, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """Evaluate a command for risk, log it, and return (is_allowed, reason)."""
        command = arguments.get('command', '')
        if not command and tool_name in ('file_write', 'file_opener'):
            command = arguments.get('path', '')
            
        is_high_risk = False
        
        # Check patterns
        for pattern in self._compiled_patterns:
            if pattern.search(command):
                is_high_risk = True
                break
                
        risk_level = "HIGH" if is_high_risk else "LOW"
        
        if is_high_risk:
            # Block and emit notification
            status = "BLOCKED"
            self._emit_dbus_notification(agent_name, command)
            self.ledger.log_execution(agent_name, tool_name, arguments, risk_level, status)
            return False, f"Command blocked by Security Sandbox (High Risk): {command}"
            
        # Allowed
        status = "ALLOWED"
        self.ledger.log_execution(agent_name, tool_name, arguments, risk_level, status)
        return True, "Command allowed"

    def _emit_dbus_notification(self, agent_name: str, command: str) -> None:
        """Emit a native desktop notification."""
        try:
            summary = "⚠️ AXIOM Security Alert"
            body = f"Intercepted High Risk Command from {agent_name}:\n{command}"
            # Use notify-send as it's the standard for Linux desktop notifications
            subprocess.run(['notify-send', '-u', 'critical', summary, body], check=False)
        except Exception as e:
            logger.error(f"Failed to emit DBus notification: {e}")
