import psutil
import time
import csv
import os
import threading
import functools
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for CPU and RAM usage tracking
    """
    
    def __init__(self, csv_directory: str = "performance_logs"):
        self.csv_directory = Path(csv_directory)
        self.csv_directory.mkdir(exist_ok=True)
        
        # CSV file paths
        self.endpoint_csv = self.csv_directory / "endpoint_performance.csv"
        self.function_csv = self.csv_directory / "function_performance.csv"
        self.system_csv = self.csv_directory / "system_performance.csv"
        
        # Thread lock for CSV writing
        self._csv_lock = threading.Lock()
        
        # System monitoring
        self._monitoring_active = False
        self._monitoring_thread = None
        self._monitoring_interval = 5  # seconds
        
        # Performance data cache
        self._performance_cache = []
        self._cache_size_limit = 1000
        
        # Initialize CSV files with headers
        self._initialize_csv_files()
        
        logger.info(f"PerformanceMonitor initialized. CSV files in: {self.csv_directory}")
    
    def _initialize_csv_files(self):
        """Initialize CSV files with appropriate headers"""
        
        # Endpoint performance CSV
        endpoint_headers = [
            'timestamp', 'endpoint', 'method', 'status_code', 'duration_ms',
            'cpu_percent_start', 'cpu_percent_end', 'cpu_percent_avg',
            'memory_mb_start', 'memory_mb_end', 'memory_mb_peak',
            'memory_percent_start', 'memory_percent_end', 'memory_percent_peak',
            'request_size_bytes', 'response_size_bytes', 'user_id', 'session_id'
        ]
        
        # Function performance CSV
        function_headers = [
            'timestamp', 'function_name', 'module', 'duration_ms',
            'cpu_percent_start', 'cpu_percent_end', 'cpu_percent_avg',
            'memory_mb_start', 'memory_mb_end', 'memory_mb_delta',
            'memory_percent_start', 'memory_percent_end',
            'args_count', 'kwargs_count', 'return_size_bytes',
            'exception_occurred', 'exception_type'
        ]
        
        # System performance CSV
        system_headers = [
            'timestamp', 'cpu_percent', 'memory_percent', 'memory_mb_used',
            'memory_mb_available', 'disk_percent', 'network_bytes_sent',
            'network_bytes_recv', 'active_connections', 'load_average_1m'
        ]
        
        # Write headers if files don't exist
        for csv_file, headers in [
            (self.endpoint_csv, endpoint_headers),
            (self.function_csv, function_headers),
            (self.system_csv, system_headers)
        ]:
            if not csv_file.exists():
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_mb_used = memory.used / (1024 * 1024)
            memory_mb_available = memory.available / (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Load average (Unix-like systems)
            try:
                load_avg = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
            except (OSError, AttributeError):
                load_avg = 0.0
            
            # Active connections (approximate)
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, OSError):
                connections = 0
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_mb_used': memory_mb_used,
                'memory_mb_available': memory_mb_available,
                'disk_percent': disk_percent,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'active_connections': connections,
                'load_average_1m': load_avg
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def _write_to_csv(self, csv_file: Path, data: Dict[str, Any]):
        """Thread-safe CSV writing"""
        try:
            with self._csv_lock:
                with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data.keys())
                    writer.writerow(data)
        except Exception as e:
            logger.error(f"Error writing to CSV {csv_file}: {e}")
    
    def log_endpoint_performance(self, endpoint: str, method: str, status_code: int,
                                duration_ms: float, metrics_start: Dict, metrics_end: Dict,
                                request_size: int = 0, response_size: int = 0,
                                user_id: str = None, session_id: str = None):
        """Log endpoint performance data"""
        
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'duration_ms': round(duration_ms, 2),
            'cpu_percent_start': metrics_start.get('cpu_percent', 0),
            'cpu_percent_end': metrics_end.get('cpu_percent', 0),
            'cpu_percent_avg': round((metrics_start.get('cpu_percent', 0) + metrics_end.get('cpu_percent', 0)) / 2, 2),
            'memory_mb_start': round(metrics_start.get('memory_mb_used', 0), 2),
            'memory_mb_end': round(metrics_end.get('memory_mb_used', 0), 2),
            'memory_mb_peak': round(max(metrics_start.get('memory_mb_used', 0), metrics_end.get('memory_mb_used', 0)), 2),
            'memory_percent_start': round(metrics_start.get('memory_percent', 0), 2),
            'memory_percent_end': round(metrics_end.get('memory_percent', 0), 2),
            'memory_percent_peak': round(max(metrics_start.get('memory_percent', 0), metrics_end.get('memory_percent', 0)), 2),
            'request_size_bytes': request_size,
            'response_size_bytes': response_size,
            'user_id': user_id or '',
            'session_id': session_id or ''
        }
        
        self._write_to_csv(self.endpoint_csv, data)
    
    def log_function_performance(self, function_name: str, module: str, duration_ms: float,
                               metrics_start: Dict, metrics_end: Dict, args_count: int = 0,
                               kwargs_count: int = 0, return_size: int = 0,
                               exception_occurred: bool = False, exception_type: str = None):
        """Log function performance data"""
        
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'function_name': function_name,
            'module': module,
            'duration_ms': round(duration_ms, 2),
            'cpu_percent_start': metrics_start.get('cpu_percent', 0),
            'cpu_percent_end': metrics_end.get('cpu_percent', 0),
            'cpu_percent_avg': round((metrics_start.get('cpu_percent', 0) + metrics_end.get('cpu_percent', 0)) / 2, 2),
            'memory_mb_start': round(metrics_start.get('memory_mb_used', 0), 2),
            'memory_mb_end': round(metrics_end.get('memory_mb_used', 0), 2),
            'memory_mb_delta': round(metrics_end.get('memory_mb_used', 0) - metrics_start.get('memory_mb_used', 0), 2),
            'memory_percent_start': round(metrics_start.get('memory_percent', 0), 2),
            'memory_percent_end': round(metrics_end.get('memory_percent', 0), 2),
            'args_count': args_count,
            'kwargs_count': kwargs_count,
            'return_size_bytes': return_size,
            'exception_occurred': exception_occurred,
            'exception_type': exception_type or ''
        }
        
        self._write_to_csv(self.function_csv, data)
    
    def log_system_performance(self):
        """Log current system performance"""
        metrics = self.get_system_metrics()
        if metrics:
            data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **metrics
            }
            self._write_to_csv(self.system_csv, data)
    
    def start_system_monitoring(self, interval: int = 5):
        """Start continuous system monitoring"""
        self._monitoring_interval = interval
        self._monitoring_active = True
        
        def monitor_loop():
            while self._monitoring_active:
                try:
                    self.log_system_performance()
                    time.sleep(self._monitoring_interval)
                except Exception as e:
                    logger.error(f"Error in system monitoring loop: {e}")
                    time.sleep(1)
        
        self._monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitoring_thread.start()
        logger.info(f"System monitoring started with {interval}s interval")
    
    def stop_system_monitoring(self):
        """Stop continuous system monitoring"""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("System monitoring stopped")
    
    @contextmanager
    def monitor_function(self, function_name: str, module: str = None, 
                        args_count: int = 0, kwargs_count: int = 0):
        """Context manager for monitoring function performance"""
        start_time = time.time()
        metrics_start = self.get_system_metrics()
        exception_occurred = False
        exception_type = None
        return_size = 0
        
        try:
            yield
        except Exception as e:
            exception_occurred = True
            exception_type = type(e).__name__
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            metrics_end = self.get_system_metrics()
            
            self.log_function_performance(
                function_name=function_name,
                module=module or 'unknown',
                duration_ms=duration_ms,
                metrics_start=metrics_start,
                metrics_end=metrics_end,
                args_count=args_count,
                kwargs_count=kwargs_count,
                return_size=return_size,
                exception_occurred=exception_occurred,
                exception_type=exception_type
            )
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary from CSV files"""
        try:
            import pandas as pd
            
            # Read recent data
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            summary = {}
            
            # Endpoint performance summary
            if self.endpoint_csv.exists():
                df = pd.read_csv(self.endpoint_csv)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                recent_df = df[df['timestamp'] >= cutoff_time]
                
                if not recent_df.empty:
                    summary['endpoints'] = {
                        'total_requests': len(recent_df),
                        'avg_duration_ms': recent_df['duration_ms'].mean(),
                        'max_duration_ms': recent_df['duration_ms'].max(),
                        'avg_cpu_usage': recent_df['cpu_percent_avg'].mean(),
                        'avg_memory_mb': recent_df['memory_mb_peak'].mean(),
                        'slowest_endpoints': recent_df.nlargest(5, 'duration_ms')[['endpoint', 'duration_ms']].to_dict('records')
                    }
            
            # Function performance summary
            if self.function_csv.exists():
                df = pd.read_csv(self.function_csv)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                recent_df = df[df['timestamp'] >= cutoff_time]
                
                if not recent_df.empty:
                    summary['functions'] = {
                        'total_calls': len(recent_df),
                        'avg_duration_ms': recent_df['duration_ms'].mean(),
                        'max_duration_ms': recent_df['duration_ms'].max(),
                        'exceptions_count': recent_df['exception_occurred'].sum(),
                        'slowest_functions': recent_df.nlargest(5, 'duration_ms')[['function_name', 'duration_ms']].to_dict('records')
                    }
            
            return summary
            
        except ImportError:
            logger.warning("pandas not available for performance summary")
            return {"error": "pandas required for performance summary"}
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return {"error": str(e)}

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Decorator for monitoring functions
def monitor_performance(func: Callable) -> Callable:
    """Decorator to monitor function performance"""
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        with performance_monitor.monitor_function(
            function_name=func.__name__,
            module=func.__module__,
            args_count=len(args),
            kwargs_count=len(kwargs)
        ):
            return func(*args, **kwargs)
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        with performance_monitor.monitor_function(
            function_name=func.__name__,
            module=func.__module__,
            args_count=len(args),
            kwargs_count=len(kwargs)
        ):
            return await func(*args, **kwargs)
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# FastAPI middleware for endpoint monitoring
class PerformanceMiddleware:
    """FastAPI middleware for monitoring endpoint performance"""
    
    def __init__(self, app, monitor: PerformanceMonitor):
        self.app = app
        self.monitor = monitor
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        metrics_start = self.monitor.get_system_metrics()
        
        # Extract request info
        method = scope.get("method", "")
        path = scope.get("path", "")
        
        # Get request size
        request_size = 0
        if "content-length" in scope.get("headers", {}):
            try:
                request_size = int(dict(scope["headers"]).get(b"content-length", b"0"))
            except (ValueError, TypeError):
                request_size = 0
        
        # Extract user info from headers or query params
        user_id = None
        session_id = None
        
        # Response tracking
        response_size = 0
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal response_size, status_code
            
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_size += len(body)
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            metrics_end = self.monitor.get_system_metrics()
            
            self.monitor.log_endpoint_performance(
                endpoint=path,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                metrics_start=metrics_start,
                metrics_end=metrics_end,
                request_size=request_size,
                response_size=response_size,
                user_id=user_id,
                session_id=session_id
            )
