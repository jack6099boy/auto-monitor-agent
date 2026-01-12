import os
from typing import Optional, Dict
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from .rag import RAGSystem
from .monitor import LogMonitor
from .config import LabConfig, AgentConfig, get_config

# Multi-lab instance caches (per-lab singletons)
_rag_systems: Dict[str, RAGSystem] = {}
_monitors: Dict[str, LogMonitor] = {}
_agents: Dict[str, any] = {}

# Default lab (backward compatibility)
_default_lab_id = "default"


def get_rag_system(lab_id: Optional[str] = None, config: Optional[LabConfig] = None) -> RAGSystem:
    """Get or create RAG system instance for a specific lab"""
    global _rag_systems

    if lab_id is None:
        lab_id = config.lab_id if config else get_config().lab.lab_id

    if lab_id not in _rag_systems:
        if config is None:
            config = get_config(lab_id).lab
        _rag_systems[lab_id] = RAGSystem(
            sop_dir=config.sop_dir,
            persist_dir=config.chroma_db_dir,
            lab_id=lab_id
        )
        try:
            _rag_systems[lab_id].build_index()
            print(f"[{lab_id}] RAG index built successfully.")
        except Exception as e:
            print(f"[{lab_id}] Error building RAG index: {e}")
    return _rag_systems[lab_id]


def get_monitor(lab_id: Optional[str] = None, config: Optional[LabConfig] = None) -> LogMonitor:
    """Get or create monitor instance for a specific lab"""
    global _monitors

    if lab_id is None:
        lab_id = config.lab_id if config else get_config().lab.lab_id

    if lab_id not in _monitors:
        if config is None:
            app_config = get_config(lab_id)
            config = app_config.lab
            auto_process = app_config.monitor.auto_process
        else:
            auto_process = False
        _monitors[lab_id] = LogMonitor(
            log_dir=config.log_dir,
            auto_process=auto_process
        )
    return _monitors[lab_id]


def _should_continue(state: MessagesState) -> str:
    """Determine if agent should continue to tools or end"""
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    if not hasattr(last_message, 'tool_calls'):
        return END

    tool_calls = last_message.tool_calls
    return "tools" if tool_calls else END


def build_agent(lab_id: Optional[str] = None, agent_config: Optional[AgentConfig] = None):
    """Build and return the agent for a specific lab (factory function)"""
    global _agents

    if lab_id is None:
        lab_id = get_config().lab.lab_id

    if lab_id in _agents:
        return _agents[lab_id]

    if agent_config is None:
        agent_config = get_config(lab_id).agent

    # Ensure lab-specific instances are initialized
    rag_system = get_rag_system(lab_id)
    monitor = get_monitor(lab_id)

    # Define tools (using shared instances via closure)
    @tool
    def query_sop(query: str) -> str:
        """Query the SOP documents for relevant information."""
        response = rag_system.query(query)
        return str(response) if response else "No relevant information found."

    @tool
    def check_logs() -> str:
        """Check for anomalies in logs."""
        with monitor._lock:  # Thread-safe access
            if monitor.anomalies:
                anomalies_str = "\n".join(monitor.anomalies)
                monitor.anomalies.clear()
                return f"Anomalies detected:\n{anomalies_str}"
            else:
                return "No anomalies detected."

    @tool
    def analyze_log_with_drain(log_content: str) -> str:
        """
        Analyze log content using Drain3 template miner.

        Args:
            log_content: Single or multi-line log content to analyze

        Returns:
            Analysis result including template match and anomaly detection
        """
        try:
            # Input validation
            if not log_content or not log_content.strip():
                return "Error: Empty log content provided"

            # Limit input size
            if len(log_content) > 10000:
                return "Error: Log content too large (max 10000 characters)"

            lines = log_content.strip().split('\n')
            results = []

            for line in lines:
                if line.strip():
                    result = monitor.template_miner.add_log_message(line.strip())

                    # Determine if anomaly
                    is_anomaly = result["change_type"] != "none"

                    analysis = {
                        "log_line": line,
                        "cluster_id": result.get("cluster_id"),
                        "template": result.get("template_mined"),
                        "is_anomaly": is_anomaly,
                        "change_type": result["change_type"]
                    }
                    results.append(analysis)

            # Format output
            if not results:
                return "No valid log lines to analyze."

            # Count anomalies
            anomaly_count = sum(1 for r in results if r["is_anomaly"])

            output = f"Analyzed {len(results)} log lines, found {anomaly_count} anomalies.\n\n"

            for r in results:
                if r["is_anomaly"]:
                    output += f"⚠️ ANOMALY DETECTED:\n"
                    output += f"  Log: {r['log_line']}\n"
                    output += f"  Template: {r['template']}\n"
                    output += f"  Change Type: {r['change_type']}\n\n"

            if anomaly_count == 0:
                output += "✅ All log lines match known patterns (no anomalies).\n"

            return output

        except Exception as e:
            return f"Error analyzing logs: {str(e)}"

    @tool
    def send_command_to_csharp(command: str, params: Optional[dict] = None) -> str:
        """
        Send a command to the C# Automation Framework.

        Args:
            command: The command name (e.g., 'return_home', 'retry_test', 'pause', 'shutdown')
            params: Optional dictionary of parameters for the command

        Returns:
            Confirmation message with Command ID
        """
        try:
            cmd_id = monitor.hint_manager.send_command(command, params)
            return f"Command '{command}' sent successfully. ID: {cmd_id}"
        except Exception as e:
            return f"Error sending command: {str(e)}"

    @tool
    def restart_csharp_app() -> str:
        """
        Attempt to restart the C# Automation Framework application.
        Requires C_SHARP_APP_PATH to be configured.
        """
        try:
            app_path = get_config().monitor.c_sharp_app_path
            if not app_path:
                return "Error: C_SHARP_APP_PATH is not configured."

            import subprocess
            import psutil

            # First, kill existing process if running
            app_name = os.path.basename(app_path)
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == app_name:
                    proc.kill()

            # Start application
            subprocess.Popen([app_path], cwd=os.path.dirname(app_path))
            return f"Application '{app_name}' restarted successfully."
        except Exception as e:
            return f"Error restarting application: {str(e)}"

    # Define call_model node
    def call_model(state: MessagesState):
        llm = ChatOpenAI(
            model=agent_config.llm_model,
            api_key=agent_config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url=agent_config.openrouter_base_url,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            top_p=agent_config.top_p
        )
        tools = [query_sop, check_logs, analyze_log_with_drain, send_command_to_csharp, restart_csharp_app]
        llm_with_tools = llm.bind_tools(tools)
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Build tool node
    tools = [query_sop, check_logs, analyze_log_with_drain, send_command_to_csharp, restart_csharp_app]
    tool_node = ToolNode(tools)

    # Build the graph
    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("agent", _should_continue)
    graph.set_entry_point("agent")

    # Compile the graph
    _agents[lab_id] = graph.compile()

    return _agents[lab_id]


def reset_agent(lab_id: Optional[str] = None):
    """Reset instances for a specific lab or all labs (useful for testing)"""
    global _rag_systems, _monitors, _agents

    if lab_id:
        # Reset specific lab
        _rag_systems.pop(lab_id, None)
        _monitors.pop(lab_id, None)
        _agents.pop(lab_id, None)
    else:
        # Reset all
        _rag_systems.clear()
        _monitors.clear()
        _agents.clear()


def list_active_labs() -> list:
    """List all active lab IDs"""
    return list(_agents.keys())


# Backward compatibility: provide module-level instances
# These are lazily initialized on first access
def __getattr__(name):
    if name == "agent":
        return build_agent()
    elif name == "rag_system":
        return get_rag_system()
    elif name == "monitor":
        return get_monitor()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    # Example usage
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "human", "content": "What is the SOP for error handling?"}]})
    print(result["messages"][-1].content)

    # POC: Test new Drain3 tool
    drain_result = agent.invoke({"messages": [{"role": "human", "content": "Analyze this log: ERROR: Connection timeout to database at 2024-01-01 10:00:00"}]})
    print("Drain3 POC:", drain_result["messages"][-1].content)
    print(result)
