import os
import time
import threading
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from .notification import NotificationManager
from .config import get_config
from .hint_manager import HintManager


class LogMonitor(FileSystemEventHandler):
    def __init__(self, log_dir=None, auto_process=None):
        self.config = get_config()
        self.log_dir = log_dir or self.config.lab.log_dir
        self.hints_dir = self.config.lab.hints_dir

        # Use config value if not provided, default to False if neither
        if auto_process is None:
            self.auto_process = self.config.monitor.auto_process
        else:
            self.auto_process = auto_process

        self.template_miner = TemplateMiner(persistence_handler=FilePersistence("drain3_state.bin"))
        self.observer = Observer()

        # Watch logs directory
        if os.path.exists(self.log_dir):
            self.observer.schedule(self, path=self.log_dir, recursive=False)
        else:
            print(f"Warning: Log directory {self.log_dir} does not exist.")

        # Watch hints directory (for user input)
        if os.path.exists(self.hints_dir):
            self.observer.schedule(self, path=self.hints_dir, recursive=False)
        else:
            os.makedirs(self.hints_dir, exist_ok=True)
            self.observer.schedule(self, path=self.hints_dir, recursive=False)

        self.anomalies = []
        self.notifier = NotificationManager()
        self.hint_manager = HintManager(self.hints_dir)
        self._lock = threading.Lock()
        self._file_positions = {}
        self._file_inodes = {}
        self._last_notification_time = {}
        self._notification_cooldown = self.config.monitor.notification_cooldown

        # Heartbeat monitoring
        self._stop_heartbeat_monitor = threading.Event()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_monitor_loop, daemon=True)

    def _should_send_notification(self, anomaly_key: str) -> bool:
        """Check if notification should be sent (rate limiting)"""
        current_time = time.time()
        last_time = self._last_notification_time.get(anomaly_key, 0)

        if current_time - last_time > self._notification_cooldown:
            self._last_notification_time[anomaly_key] = current_time
            return True
        return False

    def on_modified(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)

        if filename.endswith('.log'):
            self.process_log_file(event.src_path)
        elif filename == "user_input.json":
            self._process_user_input()

    def _process_user_input(self):
        """Process user input from C# app"""
        user_input = self.hint_manager.read_user_input()
        if user_input and "input" in user_input:
            input_text = user_input["input"]
            print(f"Received user input: {input_text}")

            # Trigger Agent to handle the input
            if self.auto_process:
                self._handle_user_command(input_text, user_input.get("user", "operator"))

    def _handle_user_command(self, input_text: str, user: str):
        """Handle user natural language command via Agent"""
        try:
            from .agent import agent
            from langchain_core.messages import HumanMessage

            query = f"""Operator Request: {input_text}

User: {user}

Please interpret this request and:
1. If it's a question, answer it using SOPs.
2. If it's a command for the automation system (e.g. 'return home', 'retry'), use the 'send_command' tool.
"""
            agent.invoke({"messages": [HumanMessage(content=query)]})

        except Exception as e:
            print(f"Error handling user command: {e}")

    def _heartbeat_monitor_loop(self):
        """Check for C# app heartbeat"""
        crash_timeout = self.config.monitor.crash_timeout
        while not self._stop_heartbeat_monitor.is_set():
            time.sleep(5)  # Check every 5 seconds

            heartbeat = self.hint_manager.get_latest_heartbeat()
            if not heartbeat:
                continue

            last_ts = heartbeat.get("timestamp", 0)
            if time.time() - last_ts > crash_timeout:
                # Heartbeat stale!
                anomaly_key = "csharp_crash"
                if self._should_send_notification(anomaly_key):
                    msg = f"C# Application Heartbeat Lost! (Last seen: {time.ctime(last_ts)})"
                    print(f"CRITICAL: {msg}")

                    if self.auto_process:
                        self._handle_crash(msg)
                    else:
                        self.notifier.send_alert(msg)

    def _handle_crash(self, msg: str):
        """Handle crash detection"""
        try:
            from .agent import agent
            from langchain_core.messages import HumanMessage

            query = f"""CRITICAL ALERT: {msg}

The C# Automation Framework appears to have crashed or frozen.
Please:
1. Analyze the situation.
2. Check if we should restart it (check config or SOPs).
3. If configured, use 'restart_csharp_app' tool.
4. Notify the operator.
"""
            agent.invoke({"messages": [HumanMessage(content=query)]})

        except Exception as e:
             self.notifier.send_alert(f"{msg}\n(Agent failed to handle crash: {e})")

    def process_log_file(self, file_path):
        with self._lock:
            # Get current file inode
            try:
                current_inode = os.stat(file_path).st_ino
            except OSError:
                return  # File deleted

            # Check for log rotation (new file)
            if file_path in self._file_inodes:
                if self._file_inodes[file_path] != current_inode:
                    print(f"Log rotation detected for {file_path}")
                    self._file_positions[file_path] = 0  # Reset position

            self._file_inodes[file_path] = current_inode

            # Read from last position
            last_pos = self._file_positions.get(file_path, 0)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Check if file was truncated
                    f.seek(0, 2)  # Move to end
                    file_size = f.tell()

                    if file_size < last_pos:
                        print(f"File truncated: {file_path}")
                        last_pos = 0

                    f.seek(last_pos)
                    new_lines = f.readlines()
                    self._file_positions[file_path] = f.tell()

                    # Process new lines
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            self._process_line(line, file_path)

            except Exception as e:
                print(f"Error processing log file {file_path}: {e}")

    def _process_line(self, line: str, file_path: str):
        """Process a single log line"""
        result = self.template_miner.add_log_message(line)
        if result["change_type"] != "none":
            anomaly = f"Anomaly detected in {file_path}: {line}"
            self.anomalies.append(anomaly)
            print(anomaly)

            # Rate limiting for notifications
            anomaly_key = f"{file_path}:{result.get('cluster_id', 'unknown')}"
            if self._should_send_notification(anomaly_key):
                if self.auto_process:
                    self._auto_handle_anomaly(line, file_path)
                else:
                    self.notifier.send_alert(anomaly)

    def _auto_handle_anomaly(self, log_line: str, file_path: str):
        """Auto-handle anomaly: invoke Agent for analysis and SOP query"""
        try:
            # Delayed import to avoid circular dependency
            from .agent import agent
            from langchain_core.messages import HumanMessage

            # Build query
            query = f"""檢測到測試異常，請協助分析：

Log 檔案: {file_path}
異常日誌: {log_line}

請執行以下步驟：
1. 使用 analyze_log_with_drain 工具分析這條日誌
2. 使用 query_sop 工具查詢相關的 SOP 處理步驟
3. 提供清晰的處理建議給測試助理

請以簡潔易懂的方式回答。"""

            # Invoke Agent
            messages = [HumanMessage(content=query)]
            result = agent.invoke({"messages": messages})

            # Get Agent response
            response = result["messages"][-1].content

            # Send notification with analysis result
            notification_message = f"""🚨 自動化測試異常通知

📍 位置: {file_path}
📝 異常日誌: {log_line}

🤖 AI 分析結果:
{response}

---
AutoTest AIOps Agent
"""
            self.notifier.send_alert(notification_message)

            # Import HintManager if available
            try:
                from .hint_manager import HintManager
                hint_mgr = HintManager()
                hint_mgr.add_hint(
                    anomaly=log_line,
                    analysis=response,
                    sop_solution=response,
                    severity="warning"
                )
            except ImportError:
                pass  # HintManager not yet implemented

        except Exception as e:
            # Agent processing failed, send basic notification
            error_msg = f"異常檢測到但自動分析失敗: {log_line}\n錯誤: {str(e)}"
            self.notifier.send_alert(error_msg)

    def start_monitoring(self):
        self.observer.start()
        self._heartbeat_thread.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
        self.observer.join()

    def stop(self):
        self.observer.stop()
        self._stop_heartbeat_monitor.set()
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)


if __name__ == "__main__":
    monitor = LogMonitor()
    monitor.start_monitoring()