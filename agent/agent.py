import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from .rag import RAGSystem
from .monitor import LogMonitor

# Initialize shared instances
rag_system = RAGSystem()
monitor = LogMonitor()

# Build RAG index
try:
    rag_system.build_index()
    print("RAG index built successfully.")
except Exception as e:
    print(f"Error building RAG index: {e}")

# Define tools
@tool
def query_sop(query: str) -> str:
    """Query the SOP documents for relevant information."""
    response = rag_system.query(query)
    return str(response) if response else "No relevant information found."


@tool
def check_logs() -> str:
    """Check for anomalies in logs."""
    if monitor.anomalies:
        anomalies_str = "\n".join(monitor.anomalies)
        monitor.anomalies.clear()
        return f"Anomalies detected:\n{anomalies_str}"
    else:
        return "No anomalies detected."


# Define nodes
def call_model(state: MessagesState):
    # Define the LLM with tuned parameters
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.3,  # Lower for more deterministic responses
        max_tokens=1000,  # Limit response length
        top_p=0.9  # Nucleus sampling for diversity
    )
    # Bind tools
    llm_with_tools = llm.bind_tools([query_sop, check_logs])
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode([query_sop, check_logs])

# Build the graph
graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", tool_node)
graph.add_edge("tools", "agent")
graph.add_conditional_edges("agent", lambda x: "tools" if x["messages"][-1].tool_calls else END)
graph.set_entry_point("agent")

# Compile the graph
agent = graph.compile()


if __name__ == "__main__":
    # Example usage
    result = agent.invoke({"messages": [{"role": "human", "content": "What is the SOP for error handling?"}]})
    print(result)