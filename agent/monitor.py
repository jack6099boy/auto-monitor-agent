import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from .notification import NotificationManager


class LogMonitor(FileSystemEventHandler):
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.template_miner = TemplateMiner(persistence_handler=FilePersistence("drain3_state.bin"))
        self.observer = Observer()
        self.observer.schedule(self, path=log_dir, recursive=False)
        self.anomalies = []
        self.notifier = NotificationManager()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.process_log_file(event.src_path)

    def process_log_file(self, file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
            for line in lines[-10:]:  # Process last 10 lines, assuming incremental changes
                line = line.strip()
                if line:
                    result = self.template_miner.add_log_message(line)
                    if result["change_type"] != "none":
                        anomaly = f"Anomaly detected in {file_path}: {line}"
                        self.anomalies.append(anomaly)
                        print(anomaly)
                        # Send notification
                        self.notifier.send_alert(anomaly)

    def start_monitoring(self):
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()


if __name__ == "__main__":
    monitor = LogMonitor()
    monitor.start_monitoring()