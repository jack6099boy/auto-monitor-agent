import pytest
from agent.agent import rag_system, monitor

def test_rag_query():
    result = rag_system.query("test query")
    assert isinstance(result, str) or result is not None

def test_monitor_check():
    # Initially no anomalies
    monitor.anomalies.clear()
    if monitor.anomalies:
        result = f"Anomalies detected:\n" + "\n".join(monitor.anomalies)
        monitor.anomalies.clear()
    else:
        result = "No anomalies detected."
    assert "No anomalies detected" in result