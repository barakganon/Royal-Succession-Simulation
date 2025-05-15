# utils/logging_config.py
"""
Centralized logging configuration for the Royal Succession Simulation.
Provides consistent logging setup across all modules.
"""

import os
import logging
import logging.handlers
import datetime
from typing import Optional

# Default log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Log levels
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# Default log format
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Performance metrics logger
performance_logger = None

def setup_logger(name: str, 
                 level: str = 'info', 
                 log_file: Optional[str] = None,
                 console_output: bool = True,
                 log_format: str = DEFAULT_LOG_FORMAT) -> logging.Logger:
    """
    Set up a logger with the specified configuration.
    
    Args:
        name: Name of the logger
        level: Log level (debug, info, warning, error, critical)
        log_file: Path to log file (if None, a default path will be used)
        console_output: Whether to output logs to console
        log_format: Format string for log messages
        
    Returns:
        Configured logger
    """
    # Get the logger
    logger = logging.getLogger(name)
    
    # Set log level
    logger.setLevel(LOG_LEVELS.get(level.lower(), logging.INFO))
    
    # Clear existing handlers to avoid duplicate logs
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Add file handler if log_file is specified or use default
    if log_file is None:
        log_file = os.path.join(LOG_DIR, f"{name.replace('.', '_')}.log")
    
    # Create file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Add console handler if requested
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def setup_performance_logger():
    """
    Set up a dedicated logger for performance metrics.
    """
    global performance_logger
    
    if performance_logger is None:
        # Create performance log file with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        perf_log_file = os.path.join(LOG_DIR, f"performance_{timestamp}.log")
        
        # Set up logger with custom format
        perf_format = '%(asctime)s - %(message)s'
        performance_logger = setup_logger(
            'royal_succession.performance',
            level='info',
            log_file=perf_log_file,
            console_output=False,
            log_format=perf_format
        )
    
    return performance_logger

def log_performance(operation: str, duration: float, details: Optional[dict] = None):
    """
    Log a performance metric.
    
    Args:
        operation: Name of the operation being measured
        duration: Duration in seconds
        details: Additional details to log
    """
    if performance_logger is None:
        setup_performance_logger()
    
    # Format the log message
    message = f"{operation}: {duration:.6f}s"
    if details:
        details_str = ", ".join(f"{k}={v}" for k, v in details.items())
        message += f" ({details_str})"
    
    performance_logger.info(message)

# Set up root logger
root_logger = setup_logger('royal_succession', level='info')

# Set up performance logger
setup_performance_logger()