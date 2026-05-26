# sla_monitor.py
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json
import requests
from database import Database
from logger import logger
from alerting import alert_manager

class SLALevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class SLAStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    TIMEOUT = "timeout"
    FAILED = "failed"

@dataclass
class SLAMetric:
    """SLA Metric data structure"""
    name: str
    level: SLALevel
    threshold_seconds: int  # Maximum allowed time in seconds
    warning_threshold: int   # Warning before timeout
    last_check: datetime
    last_duration: float
    status: SLAStatus
    history: List[float]  # List of recent durations
    
class SLAMonitor:
    """
    Monitor SLA compliance for API endpoints and sync processes
    """
    
    def __init__(self):
        self.db = Database()
        self.metrics: Dict[str, SLAMetric] = {}
        self.alert_callbacks = []
        self.running = False
        self.monitor_thread = None
        
        # Initialize default metrics
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """Initialize default SLA metrics"""
        defaults = [
            ("api.orders.sync", SLALevel.HIGH, 300, 240),      # 5 min timeout, warning at 4 min
            ("api.products.sync", SLALevel.MEDIUM, 180, 150),   # 3 min timeout, warning at 2.5 min
            ("api.stock.sync", SLALevel.HIGH, 120, 90),         # 2 min timeout, warning at 1.5 min
            ("api.transactions.sync", SLALevel.MEDIUM, 240, 180), # 4 min timeout, warning at 3 min
            ("webhook.processing", SLALevel.HIGH, 30, 20),      # 30 sec timeout, warning at 20 sec
            ("token.refresh", SLALevel.CRITICAL, 10, 7),        # 10 sec timeout, warning at 7 sec
            ("database.query", SLALevel.MEDIUM, 5, 3),          # 5 sec timeout, warning at 3 sec
            ("report.generation", SLALevel.LOW, 600, 480),      # 10 min timeout, warning at 8 min
        ]
        
        for name, level, threshold, warning in defaults:
            self.metrics[name] = SLAMetric(
                name=name,
                level=level,
                threshold_seconds=threshold,
                warning_threshold=warning,
                last_check=datetime.now(),
                last_duration=0,
                status=SLAStatus.HEALTHY,
                history=[]
            )
    
    def register_metric(self, name: str, level: SLALevel, threshold: int, warning: int):
        """Register new SLA metric"""
        self.metrics[name] = SLAMetric(
            name=name,
            level=level,
            threshold_seconds=threshold,
            warning_threshold=warning,
            last_check=datetime.now(),
            last_duration=0,
            status=SLAStatus.HEALTHY,
            history=[]
        )
        logger.info(f"Registered SLA metric: {name} (threshold: {threshold}s)")
    
    def record_duration(self, metric_name: str, duration_seconds: float):
        """Record execution duration for a metric"""
        if metric_name not in self.metrics:
            logger.warning(f"Unknown SLA metric: {metric_name}")
            return
        
        metric = self.metrics[metric_name]
        metric.last_duration = duration_seconds
        metric.last_check = datetime.now()
        
        # Add to history (keep last 100 records)
        metric.history.append(duration_seconds)
        if len(metric.history) > 100:
            metric.history.pop(0)
        
        # Check SLA compliance
        old_status = metric.status
        if duration_seconds > metric.threshold_seconds:
            metric.status = SLAStatus.TIMEOUT
            self._handle_sla_breach(metric, duration_seconds)
        elif duration_seconds > metric.warning_threshold:
            metric.status = SLAStatus.WARNING
            self._handle_sla_warning(metric, duration_seconds)
        else:
            metric.status = SLAStatus.HEALTHY
        
        # Save to database if status changed
        if old_status != metric.status:
            self._save_sla_event(metric)
    
    def _handle_sla_breach(self, metric: SLAMetric, duration: float):
        """Handle SLA breach (timeout)"""
        message = (
            f"🚨 *SLA BREACH - TIMEOUT*\n"
            f"Metric: {metric.name}\n"
            f"Level: {metric.level.value.upper()}\n"
            f"Duration: {duration:.2f}s\n"
            f"Threshold: {metric.threshold_seconds}s\n"
            f"Exceeded by: {duration - metric.threshold_seconds:.2f}s\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Send critical alert
        alert_manager.send_slack(message, color="danger")
        alert_manager.send_email(
            f"[CRITICAL] SLA Breach: {metric.name}",
            f"SLA timeout breached:\n\n{message}"
        )
        
        logger.error(f"SLA BREACH: {metric.name} took {duration:.2f}s (threshold: {metric.threshold_seconds}s)")
    
    def _handle_sla_warning(self, metric: SLAMetric, duration: float):
        """Handle SLA warning (approaching timeout)"""
        message = (
            f"⚠️ *SLA Warning*\n"
            f"Metric: {metric.name}\n"
            f"Duration: {duration:.2f}s\n"
            f"Warning threshold: {metric.warning_threshold}s\n"
            f"Timeout threshold: {metric.threshold_seconds}s"
        )
        
        alert_manager.send_slack(message, color="warning")
        logger.warning(f"SLA WARNING: {metric.name} took {duration:.2f}s")
    
    def _save_sla_event(self, metric: SLAMetric):
        """Save SLA event to database"""
        query = """
            INSERT INTO sla_events (metric_name, level, duration, status, threshold, warning_threshold, event_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        self.db.execute_query(query, (
            metric.name,
            metric.level.value,
            metric.last_duration,
            metric.status.value,
            metric.threshold_seconds,
            metric.warning_threshold,
            datetime.now()
        ))
    
    def get_sla_report(self, metric_name: Optional[str] = None, hours: int = 24) -> Dict:
        """Generate SLA compliance report"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if metric_name:
            query = """
                SELECT status, COUNT(*) as count, AVG(duration) as avg_duration,
                       MAX(duration) as max_duration, MIN(duration) as min_duration
                FROM sla_events
                WHERE metric_name = %s AND event_time >= %s
                GROUP BY status
            """
            cursor = self.db.execute_query(query, (metric_name, cutoff_time))
        else:
            query = """
                SELECT metric_name, status, COUNT(*) as count, AVG(duration) as avg_duration
                FROM sla_events
                WHERE event_time >= %s
                GROUP BY metric_name, status
            """
            cursor = self.db.execute_query(query, (cutoff_time,))
        
        results = cursor.fetchall()
        
        report = {
            "period_hours": hours,
            "generated_at": datetime.now().isoformat(),
            "summary": {}
        }
        
        for row in results:
            if metric_name:
                report["summary"][row[0]] = {
                    "count": row[1],
                    "avg_duration": round(row[2], 2) if row[2] else 0,
                    "max_duration": round(row[3], 2) if row[3] else 0,
                    "min_duration": round(row[4], 2) if row[4] else 0
                }
            else:
                if row[0] not in report["summary"]:
                    report["summary"][row[0]] = {}
                report["summary"][row[0]][row[1]] = {
                    "count": row[2],
                    "avg_duration": round(row[3], 2) if row[3] else 0
                }
        
        # Add current metrics status
        report["current_status"] = {}
        for name, metric in self.metrics.items():
            if not metric_name or metric_name == name:
                report["current_status"][name] = {
                    "status": metric.status.value,
                    "last_duration": round(metric.last_duration, 2),
                    "threshold": metric.threshold_seconds,
                    "warning_threshold": metric.warning_threshold,
                    "level": metric.level.value,
                    "last_check": metric.last_check.isoformat()
                }
        
        return report
    
    def start_background_monitoring(self, interval_seconds: int = 60):
        """Start background SLA monitoring thread"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval_seconds,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info(f"SLA Monitor started with interval {interval_seconds}s")
    
    def _monitor_loop(self, interval: int):
        """Background monitoring loop"""
        while self.running:
            try:
                self._check_stalled_processes()
                self._check_health_trends()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"SLA Monitor error: {e}")
    
    def _check_stalled_processes(self):
        """Check for stalled/long-running processes"""
        query = """
            SELECT brand_id, data_type, started_at
            FROM sync_logs
            WHERE status = 'running'
            AND started_at < NOW() - INTERVAL '10 minutes'
        """
        
        cursor = self.db.execute_query(query)
        stalled = cursor.fetchall()
        
        for row in stalled:
            brand_id, data_type, started_at = row
            stalled_minutes = (datetime.now() - started_at).total_seconds() / 60
            
            alert_manager.send_slack(
                f"🔴 *Stalled Process Detected*\n"
                f"Brand: {brand_id}\n"
                f"Type: {data_type}\n"
                f"Running for: {stalled_minutes:.1f} minutes\n"
                f"Started at: {started_at}",
                color="danger"
            )
    
    def _check_health_trends(self):
        """Analyze health trends and predict potential issues"""
        for name, metric in self.metrics.items():
            if len(metric.history) >= 10:
                # Calculate trend
                recent_avg = sum(metric.history[-5:]) / 5
                older_avg = sum(metric.history[-10:-5]) / 5
                
                trend_percent = ((recent_avg - older_avg) / older_avg) * 100 if older_avg > 0 else 0
                
                # Alert if trend shows significant degradation
                if trend_percent > 50 and recent_avg > metric.warning_threshold * 0.8:
                    alert_manager.send_slack(
                        f"📈 *Degradation Trend Detected*\n"
                        f"Metric: {name}\n"
                        f"Performance degraded by {trend_percent:.1f}%\n"
                        f"Recent avg: {recent_avg:.2f}s\n"
                        f"Previous avg: {older_avg:.2f}s\n"
                        f"Warning threshold: {metric.warning_threshold}s",
                        color="warning"
                    )
    
    def stop(self):
        """Stop background monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("SLA Monitor stopped")

# Decorator for SLA monitoring
def monitor_sla(metric_name: str):
    """Decorator to automatically monitor function SLA"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_sla_monitor()
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                monitor.record_duration(metric_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                monitor.record_duration(metric_name, duration)
                raise e
        return wrapper
    return decorator

# Global SLA monitor instance
_sla_monitor = None

def get_sla_monitor() -> SLAMonitor:
    global _sla_monitor
    if _sla_monitor is None:
        _sla_monitor = SLAMonitor()
    return _sla_monitor