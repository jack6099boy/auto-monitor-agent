import os
import json
import time
import shutil
import tempfile
import threading
from unittest.mock import MagicMock, patch
import pytest
from agent.monitor import LogMonitor
from agent.hint_manager import HintManager
from agent.config import get_config, AppConfig, LabConfig, AgentConfig, MonitorConfig

@pytest.fixture
def mock_config():
    """Create a temporary configuration for testing"""
    temp_dir = tempfile.mkdtemp()
    log_dir = os.path.join(temp_dir, "logs")
    hints_dir = os.path.join(temp_dir, "hints")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(hints_dir, exist_ok=True)

    # Mock config object
    lab_config = LabConfig(
        lab_id="test_lab",
        lab_name="Test Lab",
        sop_dir=os.path.join(temp_dir, "sop"),
        log_dir=log_dir,
        hints_dir=hints_dir,
        chroma_db_dir=os.path.join(temp_dir, "chroma"),
        drain3_state_file=os.path.join(temp_dir, "drain3.bin")
    )
    monitor_config = MonitorConfig(
        auto_process=True,
        notification_cooldown=0,
        crash_timeout=2  # Short timeout for testing
    )
    agent_config = AgentConfig()

    app_config = AppConfig(lab=lab_config, agent=agent_config, monitor=monitor_config)

    # Patch get_config to return our mock
    with patch("agent.monitor.get_config", return_value=app_config), \
         patch("agent.hint_manager.get_config", return_value=app_config), \
         patch("agent.agent.get_config", return_value=app_config):
        yield app_config, temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)

def test_hint_manager_commands(mock_config):
    """Test sending commands via HintManager"""
    config, _ = mock_config
    hint_mgr = HintManager(config.lab.hints_dir)

    # Send command
    cmd_id = hint_mgr.send_command("return_home", {"force": True})
    assert cmd_id is not None

    # Verify file content
    with open(config.lab.commands_file, 'r') as f:
        commands = json.load(f)

    assert len(commands) == 1
    assert commands[0]["command"] == "return_home"
    assert commands[0]["params"]["force"] is True

def test_monitor_heartbeat_crash(mock_config):
    """Test monitor detecting stale heartbeat"""
    config, _ = mock_config

    # Setup heartbeat file with old timestamp
    heartbeat_data = {
        "timestamp": time.time() - 10,  # 10s ago (timeout is 2s)
        "pid": 1234,
        "status": "running"
    }
    with open(config.lab.heartbeat_file, 'w') as f:
        json.dump(heartbeat_data, f)

    # Start monitor
    monitor = LogMonitor(log_dir=config.lab.log_dir, auto_process=True)

    # Mock agent invocation to verify it's called
    with patch("agent.agent.agent.invoke") as mock_agent:
        mock_agent.return_value = {"messages": [MagicMock(content="Crash handled")]}

        # Start heartbeat monitoring thread manually to control execution
        stop_event = threading.Event()
        monitor._stop_heartbeat_monitor = stop_event

        # Run one iteration of the loop logic
        heartbeat = monitor.hint_manager.get_latest_heartbeat()
        assert heartbeat is not None

        # Simulate check logic directly to avoid waiting/threading issues in test
        last_ts = heartbeat.get("timestamp", 0)
        if time.time() - last_ts > config.monitor.crash_timeout:
             monitor._handle_crash("Test Crash")

        # Verify agent was called
        assert mock_agent.called
        args, _ = mock_agent.call_args
        assert "CRITICAL ALERT" in args[0]["messages"][0].content

def test_monitor_user_input(mock_config):
    """Test monitor detecting user input"""
    config, _ = mock_config

    # Setup user input
    input_data = {
        "timestamp": time.time(),
        "input": "Go home",
        "user": "tester"
    }
    with open(config.lab.user_input_file, 'w') as f:
        json.dump(input_data, f)

    monitor = LogMonitor(log_dir=config.lab.log_dir, auto_process=True)

    # Mock agent
    with patch("agent.agent.agent.invoke") as mock_agent:
        mock_agent.return_value = {"messages": [MagicMock(content="Command sent")]}

        # Process input
        monitor._process_user_input()

        # Verify input file cleared
        with open(config.lab.user_input_file, 'r') as f:
            data = json.load(f)
        assert data == {}

        # Verify agent called
        assert mock_agent.called
        args, _ = mock_agent.call_args
        assert "Go home" in args[0]["messages"][0].content

if __name__ == "__main__":
    # Manually run tests if executed directly
    pass
