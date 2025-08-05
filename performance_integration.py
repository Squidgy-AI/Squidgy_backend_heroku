"""
Performance monitoring integration for main.py
This module provides easy integration of performance monitoring into your FastAPI application.
"""

from performance_monitor import performance_monitor, monitor_performance, PerformanceMiddleware
from fastapi import FastAPI, Request, Response
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

def setup_performance_monitoring(app: FastAPI):
    """
    Set up comprehensive performance monitoring for the FastAPI application
    
    Args:
        app: FastAPI application instance
    """
    
    # Add performance middleware
    app.add_middleware(PerformanceMiddleware, monitor=performance_monitor)
    
    # Start system monitoring
    performance_monitor.start_system_monitoring(interval=10)  # Every 10 seconds
    
    logger.info("Performance monitoring setup complete")
    
    # Add performance endpoints
    @app.get("/api/performance/summary")
    async def get_performance_summary(hours: int = 24):
        """Get performance summary for the last N hours"""
        try:
            summary = performance_monitor.get_performance_summary(hours=hours)
            return {
                "status": "success",
                "summary": summary,
                "hours_analyzed": hours
            }
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @app.get("/api/performance/metrics")
    async def get_current_metrics():
        """Get current system metrics"""
        try:
            metrics = performance_monitor.get_system_metrics()
            return {
                "status": "success",
                "metrics": metrics,
                "timestamp": performance_monitor.get_system_metrics().get('timestamp')
            }
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @app.post("/api/performance/start-monitoring")
    async def start_monitoring(interval: int = 10):
        """Start or restart system monitoring with specified interval"""
        try:
            performance_monitor.stop_system_monitoring()
            performance_monitor.start_system_monitoring(interval=interval)
            return {
                "status": "success",
                "message": f"System monitoring started with {interval}s interval"
            }
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @app.post("/api/performance/stop-monitoring")
    async def stop_monitoring():
        """Stop system monitoring"""
        try:
            performance_monitor.stop_system_monitoring()
            return {
                "status": "success",
                "message": "System monitoring stopped"
            }
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

def add_monitoring_to_functions():
    """
    Decorator factory to add monitoring to specific functions
    Use this to monitor critical functions in your application
    """
    return monitor_performance

# Shutdown handler
def cleanup_performance_monitoring():
    """Clean up performance monitoring on application shutdown"""
    try:
        performance_monitor.stop_system_monitoring()
        logger.info("Performance monitoring cleanup complete")
    except Exception as e:
        logger.error(f"Error during performance monitoring cleanup: {e}")

# Context manager for monitoring specific code blocks
def monitor_code_block(name: str, module: str = "main"):
    """
    Context manager for monitoring specific code blocks
    
    Usage:
        with monitor_code_block("database_query"):
            # Your code here
            result = some_database_operation()
    """
    return performance_monitor.monitor_function(name, module)

# Helper function to monitor async functions manually
async def monitor_async_function(func, *args, **kwargs):
    """
    Helper to manually monitor async functions
    
    Usage:
        result = await monitor_async_function(my_async_func, arg1, arg2, kwarg1=value1)
    """
    with performance_monitor.monitor_function(
        function_name=func.__name__,
        module=func.__module__,
        args_count=len(args),
        kwargs_count=len(kwargs)
    ):
        return await func(*args, **kwargs)

# Helper function to monitor sync functions manually  
def monitor_sync_function(func, *args, **kwargs):
    """
    Helper to manually monitor sync functions
    
    Usage:
        result = monitor_sync_function(my_sync_func, arg1, arg2, kwarg1=value1)
    """
    with performance_monitor.monitor_function(
        function_name=func.__name__,
        module=func.__module__,
        args_count=len(args),
        kwargs_count=len(kwargs)
    ):
        return func(*args, **kwargs)

# Batch monitoring decorator for multiple functions
def monitor_class_methods(cls):
    """
    Class decorator to monitor all methods of a class
    
    Usage:
        @monitor_class_methods
        class MyClass:
            def method1(self):
                pass
    """
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and not attr_name.startswith('_'):
            setattr(cls, attr_name, monitor_performance(attr))
    return cls

# Performance monitoring configuration
PERFORMANCE_CONFIG = {
    "csv_directory": "performance_logs",
    "system_monitoring_interval": 10,  # seconds
    "enable_function_monitoring": True,
    "enable_endpoint_monitoring": True,
    "enable_system_monitoring": True,
    "csv_rotation_days": 7,  # Keep CSV files for 7 days
}

def get_performance_config():
    """Get current performance monitoring configuration"""
    return PERFORMANCE_CONFIG.copy()

def update_performance_config(**kwargs):
    """Update performance monitoring configuration"""
    PERFORMANCE_CONFIG.update(kwargs)
    logger.info(f"Performance config updated: {kwargs}")
