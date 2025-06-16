"""Performance monitoring utilities."""

import time
import functools
from typing import Callable, Any
from config import logger


def timeit(func: Callable) -> Callable:
    """Decorator to measure function execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} completed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f} seconds: {e}")
            raise
    return wrapper


class PerformanceMonitor:
    """Context manager for monitoring performance of code blocks."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"{self.operation_name} completed in {duration:.2f} seconds")
        else:
            logger.error(f"{self.operation_name} failed after {duration:.2f} seconds")


def log_memory_usage():
    """Log current memory usage if psutil is available."""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.debug(f"Memory usage: {memory_mb:.1f} MB")
    except ImportError:
        logger.debug("psutil not available for memory monitoring")
    except Exception as e:
        logger.debug(f"Error checking memory usage: {e}")
