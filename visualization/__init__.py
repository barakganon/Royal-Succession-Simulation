# visualization/__init__.py
# This file makes the 'visualization' directory a Python package.

from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.visualization')
logger.debug("Visualization package initialized.")