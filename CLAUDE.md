# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoTest AIOps Agent is an intelligent automated testing operations system designed for monitoring test interruptions, handling log anomalies, and providing SOP-based remediation suggestions. The system integrates log monitoring, RAG knowledge base, and LLM Agent capabilities.

**Core Context**: This project addresses pain points in C#-based automated testing workflows (involving phone fixtures, image capture, etc.) by building a Python-based intelligent monitoring and fault tolerance system.

**Status**: Production-ready with auto-trigger anomaly handling, thread-safe operations, and multi-lab support.

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# Install test dependencies
pip install pytest
```

### Running the System
```bash
# Load environment variables and run tests
source venv/bin/activate
export $(grep -v '^#' .env | xargs)

# Run demo (creates fake SOP/logs, initializes system, simulates anomaly detection)
python demo.py

# Run tests
pytest -v

# Run specific test file
pytest tests/test_agent.py
pytest tests/test_monitor.py
pytest tests/test_rag.py
pytest tests/test_integration.py
```

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Build Docker image manually
docker build -t autotest-aiops-agent .

# Run container
docker run -d --env-file .env autotest-aiops-agent
```

## Architecture Overview

### System Components

| Component | File | Model/Technology | Purpose |
|-----------|------|------------------|---------|
| **Agent** | `agent/agent.py` | GPT-4o-mini (OpenRouter) | Tool orchestration, decision making |
| **RAG Embedding** | `agent/rag.py` | bge-large-zh-v1.5 (HuggingFace) | Document vectorization |
| **RAG Query** | `agent/rag.py` | GPT-4o-mini (OpenRouter) | Response generation |
| **Log Mining** | `agent/monitor.py` | Drain3 | Log template mining, anomaly detection |
| **Vector Store** | `agent/rag.py` | Chroma | Persistent vector database |
| **Config** | `agent/config.py` | - | Multi-lab configuration management |
| **Hints** | `agent/hint_manager.py` | - | Test screen prompt interface |

### Four-Layer System Design

1. **Monitoring Layer** (`agent/monitor.py`)
   - Watchdog for real-time file system monitoring
   - Drain3 for log template mining and anomaly detection
   - **Thread-safe**: Uses `threading.Lock` for concurrent access
   - **Position tracking**: Only processes new log content (inode-based)
   - **Rate limiting**: 5-minute notification cooldown
   - **Auto-trigger**: Automatically invokes Agent on anomaly detection
   - Persists Drain3 state to `drain3_state.bin`

2. **Knowledge Layer** (`agent/rag.py`)
   - Docling: Extracts content from SOP files (PDF, PPTX, DOCX, Markdown)
   - Chroma: Vector database for embeddings (persisted to `./chroma_db/`)
   - LlamaIndex: Query engine framework
   - **Smart indexing**: Loads existing index if documents unchanged (hash-based)
   - **Multi-lab support**: Separate collections per lab_id
   - **Incremental update**: `add_document()` for single file additions

3. **Agent Layer** (`agent/agent.py`)
   - LangGraph: Hybrid-mode Agent orchestration
   - **Lazy initialization**: Factory functions, no module-level side effects
   - **Singleton pattern**: `get_rag_system()`, `get_monitor()`, `build_agent()`
   - Tool nodes: `query_sop`, `check_logs`, `analyze_log_with_drain`
   - Conditional routing: Agent autonomously decides tool usage

4. **Configuration Layer** (`agent/config.py`)
   - `LabConfig`: Lab-specific settings (SOP dir, log dir, Chroma path)
   - `AgentConfig`: LLM parameters (model, temperature, max_tokens)
   - `MonitorConfig`: Monitor settings (auto_process, cooldown)
   - Environment variable based with sensible defaults

### Data Flow (Auto-Trigger Mode)
```
Log Files → Watchdog → Position Tracking → Drain3 → Anomaly Detection
                                                          ↓
                                              ┌───── Rate Limit Check
                                              ↓
                                    Auto-Trigger Agent (LangGraph)
                                              ↓
                       ┌──────────────────────┼──────────────────────┐
                       ↓                      ↓                      ↓
              analyze_log_with_drain     query_sop              check_logs
                       ↓                      ↓                      ↓
                  Drain3 Analysis        RAG System            Anomaly List
                       ↓                      ↓                      ↓
                       └──────────────────────┼──────────────────────┘
                                              ↓
                                    Agent Final Response
                                              ↓
                       ┌──────────────────────┼──────────────────────┐
                       ↓                      ↓                      ↓
                  Notification           HintManager             History
                  (Slack/Email)     (hints/current_hints.json)   (.jsonl)
                                              ↓
                                    Test Screen Display
```

## Key Technical Details

### Agent Tool System
- Tools defined with `@tool` decorator inside `build_agent()` factory function
- `query_sop`: Queries RAG system for SOP documentation
- `check_logs`: Thread-safe retrieval and clearing of anomaly list
- `analyze_log_with_drain`: Drain3 analysis with input validation (max 10000 chars)
- Agent autonomously decides which tools to use based on context

### RAG System Workflow
1. `build_index()`: Smart loading - checks if index exists and documents unchanged
2. `_documents_unchanged()`: Hash-based comparison for change detection
3. `load_documents()`: Docling DocumentConverter extracts text with metadata
4. `query()`: LlamaIndex query engine with OpenRouter LLM
5. `add_document()`: Incremental single document addition

### Log Monitoring Workflow
1. Watchdog Observer monitors `logs/` directory for file modifications
2. `process_log_file()`: Thread-safe with Lock, tracks file positions
3. Only new content processed (seeks to last position)
4. Log rotation detection via inode tracking
5. Rate-limited notifications (5-minute cooldown per anomaly type)
6. Auto-trigger mode: Invokes Agent for analysis and SOP lookup

### HintManager System (`agent/hint_manager.py`)
- Writes hints to `hints/current_hints.json` for test screen integration
- Maintains history in `hints/hints_history.jsonl`
- Supports severity levels: info, warning, error
- Mark resolved / clear all functionality

## Environment Variables

Required in `.env` file:
```bash
OPENROUTER_API_KEY=<your-key>      # Required for LLM and RAG

# Optional - Multi-lab configuration
LAB_ID=default                      # Lab identifier
LAB_DEFAULT_SOP_DIR=sop             # SOP directory
LAB_DEFAULT_LOG_DIR=logs            # Log directory

# Optional - Agent tuning
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=1000

# Optional - Monitor settings
MONITOR_AUTO_PROCESS=false          # Auto-trigger Agent on anomaly
MONITOR_NOTIFICATION_COOLDOWN=300   # Seconds between notifications

# Optional - Notifications
SLACK_BOT_TOKEN=<token>
SLACK_CHANNEL=#alerts
EMAIL_SERVER=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=<email>
EMAIL_PASSWORD=<password>
EMAIL_TO=<recipient>
```

## Directory Structure

```
project2/
├── agent/
│   ├── agent.py          # LangGraph Agent with factory functions
│   ├── monitor.py        # Thread-safe log monitoring
│   ├── rag.py            # Smart RAG with caching
│   ├── config.py         # Multi-lab configuration
│   ├── hint_manager.py   # Test screen hints
│   ├── notification.py   # Slack/Email alerts
│   └── metrics.py        # System metrics
├── tests/                # Unit and integration tests
├── logs/                 # Monitored log files
├── sop/                  # SOP documents (PDF, PPTX, MD)
├── hints/                # Generated hints for test screen
├── chroma_db/            # Persisted vector database
├── plans/                # Architecture plans
├── demo.py               # E2E demonstration
└── docker-compose.yml    # Container deployment
```

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- Runs on push to `main`/`develop` and PRs to `main`
- Test job: Installs dependencies and runs pytest
- Build-and-deploy job: Builds Docker image, pushes to Docker Hub

## Models Used

| Function | Model | Provider | Purpose |
|----------|-------|----------|---------|
| Agent Orchestration | gpt-4o-mini | OpenRouter | Tool decisions, response generation |
| RAG Query Engine | gpt-4o-mini | OpenRouter | SOP query responses |
| Document Embedding | bge-large-zh-v1.5 | HuggingFace | Chinese text vectorization |
| Log Analysis | Drain3 | Local | Log template mining (no LLM) |

## Important Notes

- **Lazy initialization**: Agent/RAG/Monitor created on first access, not at import
- **Thread safety**: All shared state protected by `threading.Lock`
- **Smart caching**: RAG index only rebuilt when documents change
- **Rate limiting**: Notifications throttled to prevent alert fatigue
- **Backward compatible**: Module-level `agent`, `rag_system`, `monitor` still work
- **Multi-lab ready**: Configure via `LAB_ID` environment variable
- LLM parameters: `temperature=0.3`, `max_tokens=1000`, `top_p=0.9`

## Known Limitations

- **PPT/PDF images**: Currently extracts text only, images not processed
- **Future**: Multi-modal RAG with GPT-4V for image understanding
