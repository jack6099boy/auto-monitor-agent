import json
import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from .config import get_config


class HintManager:
    """Manage hints, commands, and status for test execution screen and C# integration"""

    def __init__(self, hints_dir: Optional[str] = None):
        if hints_dir:
            self.hints_dir = hints_dir
        else:
            self.hints_dir = get_config().lab.hints_dir

        os.makedirs(self.hints_dir, exist_ok=True)
        self.config = get_config().lab

        # Files are now defined in config, but we can also use defaults relative to hints_dir
        self.current_hints_file = os.path.join(self.hints_dir, "current_hints.json")
        self.hints_history_file = os.path.join(self.hints_dir, "hints_history.jsonl")
        self.commands_file = self.config.commands_file
        self.heartbeat_file = self.config.heartbeat_file
        self.user_input_file = self.config.user_input_file
        self.acks_file = self.config.acks_file

    def send_command(self, command: str, params: Dict[str, Any] = None, priority: str = "normal") -> str:
        """
        Send a command to the C# application

        Args:
            command: Command name (e.g., "return_home")
            params: Command parameters
            priority: Priority level

        Returns:
            Command ID
        """
        cmd_id = str(uuid.uuid4())
        cmd = {
            "id": cmd_id,
            "timestamp": time.time(),
            "command": command,
            "params": params or {},
            "priority": priority
        }

        # Read existing commands
        commands = []
        if os.path.exists(self.commands_file):
            try:
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    commands = json.load(f)
            except (json.JSONDecodeError, IOError):
                commands = []

        # Append new command
        commands.append(cmd)

        # Write back
        with open(self.commands_file, 'w', encoding='utf-8') as f:
            json.dump(commands, f, ensure_ascii=False, indent=2)

        return cmd_id

    def get_latest_heartbeat(self) -> Optional[Dict[str, Any]]:
        """Get the latest heartbeat status from C# app"""
        if not os.path.exists(self.heartbeat_file):
            return None

        try:
            with open(self.heartbeat_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def read_user_input(self) -> Optional[Dict[str, Any]]:
        """Read and clear user input from C# app"""
        if not os.path.exists(self.user_input_file):
            return None

        try:
            with open(self.user_input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Clear file after reading (atomic-ish)
            with open(self.user_input_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

            if not data:
                return None

            return data
        except (json.JSONDecodeError, IOError):
            return None

    def read_acks(self) -> List[Dict[str, Any]]:
        """Read acknowledgments from C# app"""
        if not os.path.exists(self.acks_file):
            return []

        try:
            with open(self.acks_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def add_hint(self, anomaly: str, analysis: str, sop_solution: str, severity: str = "warning"):
        """
        Add a new hint

        Args:
            anomaly: Anomaly description
            analysis: AI analysis result
            sop_solution: SOP solution
            severity: Severity level (info/warning/error)
        """
        hint = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "anomaly": anomaly,
            "analysis": analysis,
            "sop_solution": sop_solution,
            "status": "unresolved"
        }

        # Update current hints file
        self._update_current_hints(hint)

        # Append to history
        self._append_to_history(hint)

    def _update_current_hints(self, hint: Dict[str, Any]):
        """Update current hints file (keep only unresolved hints)"""
        # Read existing hints
        current_hints = []
        if os.path.exists(self.current_hints_file):
            try:
                with open(self.current_hints_file, 'r', encoding='utf-8') as f:
                    current_hints = json.load(f)
            except (json.JSONDecodeError, IOError):
                current_hints = []

        # Add new hint
        current_hints.append(hint)

        # Keep only last 10 unresolved hints
        current_hints = [h for h in current_hints if h["status"] == "unresolved"][-10:]

        # Write back
        with open(self.current_hints_file, 'w', encoding='utf-8') as f:
            json.dump(current_hints, f, ensure_ascii=False, indent=2)

    def _append_to_history(self, hint: Dict[str, Any]):
        """Append to history (JSONL format)"""
        with open(self.hints_history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(hint, ensure_ascii=False) + '\n')

    def get_current_hints(self) -> List[Dict[str, Any]]:
        """Get all current unresolved hints"""
        if os.path.exists(self.current_hints_file):
            try:
                with open(self.current_hints_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def mark_resolved(self, timestamp: str):
        """Mark a hint as resolved"""
        hints = self.get_current_hints()
        for hint in hints:
            if hint["timestamp"] == timestamp:
                hint["status"] = "resolved"

        # Remove resolved hints from current file
        unresolved_hints = [h for h in hints if h["status"] == "unresolved"]
        with open(self.current_hints_file, 'w', encoding='utf-8') as f:
            json.dump(unresolved_hints, f, ensure_ascii=False, indent=2)

    def clear_all_hints(self):
        """Clear all current hints"""
        with open(self.current_hints_file, 'w', encoding='utf-8') as f:
            json.dump([], f)

    def get_hint_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        """Get hints filtered by severity"""
        hints = self.get_current_hints()
        return [h for h in hints if h["severity"] == severity]

    def get_latest_hint(self) -> Dict[str, Any] | None:
        """Get the most recent hint"""
        hints = self.get_current_hints()
        return hints[-1] if hints else None


if __name__ == "__main__":
    # Example usage
    hint_mgr = HintManager()

    # Add a test hint
    hint_mgr.add_hint(
        anomaly="ERROR: Database connection timeout",
        analysis="Database connection failed due to network issues",
        sop_solution="1. Check network connectivity\n2. Restart database service\n3. Verify connection string",
        severity="error"
    )

    # Get current hints
    hints = hint_mgr.get_current_hints()
    print(f"Current hints: {len(hints)}")
    for hint in hints:
        print(f"  - {hint['severity']}: {hint['anomaly']}")
