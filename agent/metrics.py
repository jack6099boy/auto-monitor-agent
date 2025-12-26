import psutil
import time
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics_history = []

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect basic system performance metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_used_mb': psutil.virtual_memory().used / 1024 / 1024,
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'uptime_seconds': time.time() - self.start_time
        }

    def collect_agent_metrics(self) -> Dict[str, Any]:
        """Collect agent-specific metrics (placeholder for future implementation)."""
        return {
            'active_processes': len(psutil.pids()),
            'network_connections': len(psutil.net_connections())
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics."""
        metrics = {}
        metrics.update(self.collect_system_metrics())
        metrics.update(self.collect_agent_metrics())
        metrics['timestamp'] = time.time()
        self.metrics_history.append(metrics)
        return metrics

    def log_metrics(self):
        """Log current metrics."""
        metrics = self.get_all_metrics()
        logger.info(f"Performance Metrics: {metrics}")

    def check_thresholds(self, thresholds: Dict[str, float]) -> Dict[str, bool]:
        """Check if metrics exceed thresholds."""
        metrics = self.get_all_metrics()
        alerts = {}
        for key, threshold in thresholds.items():
            if key in metrics and metrics[key] > threshold:
                alerts[key] = True
                logger.warning(f"Threshold exceeded for {key}: {metrics[key]} > {threshold}")
            else:
                alerts[key] = False
        return alerts

# Global instance
performance_monitor = PerformanceMonitor()

if __name__ == "__main__":
    # Example usage
    monitor = PerformanceMonitor()
    while True:
        monitor.log_metrics()
        time.sleep(60)  # Log every minute