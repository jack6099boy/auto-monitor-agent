import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LabConfig:
    """Lab-specific configuration"""
    lab_id: str
    lab_name: str
    sop_dir: str
    log_dir: str
    hints_dir: str  # New: Directory for C# integration files
    chroma_db_dir: str
    drain3_state_file: str
    notification_channels: List[str] = field(default_factory=lambda: ['email'])

    @property
    def heartbeat_file(self) -> str:
        return os.path.join(self.hints_dir, "heartbeat.json")

    @property
    def commands_file(self) -> str:
        return os.path.join(self.hints_dir, "commands.json")

    @property
    def user_input_file(self) -> str:
        return os.path.join(self.hints_dir, "user_input.json")

    @property
    def acks_file(self) -> str:
        return os.path.join(self.hints_dir, "acks.json")

    @classmethod
    def from_env(cls, lab_id: Optional[str] = None):
        """Load configuration from environment variables"""
        lab_id = lab_id or os.getenv("LAB_ID", "default")
        lab_upper = lab_id.upper().replace("-", "_")

        return cls(
            lab_id=lab_id,
            lab_name=os.getenv(f"LAB_{lab_upper}_NAME", f"Lab {lab_id}"),
            sop_dir=os.getenv(f"LAB_{lab_upper}_SOP_DIR", f"sop/{lab_id}" if lab_id != "default" else "sop"),
            log_dir=os.getenv(f"LAB_{lab_upper}_LOG_DIR", f"logs/{lab_id}" if lab_id != "default" else "logs"),
            hints_dir=os.getenv(f"LAB_{lab_upper}_HINTS_DIR", f"hints/{lab_id}" if lab_id != "default" else "hints"),
            chroma_db_dir=os.getenv(f"LAB_{lab_upper}_CHROMA_DB", f"chroma_db/{lab_id}" if lab_id != "default" else "./chroma_db"),
            drain3_state_file=os.getenv(f"LAB_{lab_upper}_DRAIN3_STATE", f"drain3_state_{lab_id}.bin" if lab_id != "default" else "drain3_state.bin"),
            notification_channels=os.getenv(f"LAB_{lab_upper}_NOTIFICATION_CHANNELS", "email").split(",")
        )


@dataclass
class AgentConfig:
    """Agent configuration"""
    llm_model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000
    top_p: float = 0.9
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        )


@dataclass
class MonitorConfig:
    """Monitor configuration"""
    auto_process: bool = False
    notification_cooldown: int = 300  # 5 minutes
    max_anomalies: int = 1000
    crash_timeout: int = 30  # Seconds before considering heartbeat stale
    c_sharp_app_path: str = ""  # Path to C# executable for restart

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            auto_process=os.getenv("MONITOR_AUTO_PROCESS", "false").lower() == "true",
            notification_cooldown=int(os.getenv("MONITOR_NOTIFICATION_COOLDOWN", "300")),
            max_anomalies=int(os.getenv("MONITOR_MAX_ANOMALIES", "1000")),
            crash_timeout=int(os.getenv("MONITOR_CRASH_TIMEOUT", "30")),
            c_sharp_app_path=os.getenv("C_SHARP_APP_PATH", "")
        )


@dataclass
class AppConfig:
    """Application-wide configuration"""
    lab: LabConfig
    agent: AgentConfig
    monitor: MonitorConfig

    @classmethod
    def from_env(cls, lab_id: Optional[str] = None):
        """Load all configurations from environment variables"""
        return cls(
            lab=LabConfig.from_env(lab_id),
            agent=AgentConfig.from_env(),
            monitor=MonitorConfig.from_env()
        )


# Global configuration instance (lazy loaded)
_config: Optional[AppConfig] = None


def get_config(lab_id: Optional[str] = None) -> AppConfig:
    """Get or create the global configuration instance"""
    global _config
    if _config is None:
        _config = AppConfig.from_env(lab_id)
    return _config


def reset_config():
    """Reset the global configuration (useful for testing)"""
    global _config
    _config = None


if __name__ == "__main__":
    # Example usage
    config = get_config()
    print(f"Lab ID: {config.lab.lab_id}")
    print(f"Lab Name: {config.lab.lab_name}")
    print(f"SOP Dir: {config.lab.sop_dir}")
    print(f"Log Dir: {config.lab.log_dir}")
    print(f"LLM Model: {config.agent.llm_model}")
    print(f"Auto Process: {config.monitor.auto_process}")
