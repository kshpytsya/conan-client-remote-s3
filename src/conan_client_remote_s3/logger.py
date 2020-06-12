import logging
import os

logger = logging.getLogger(__package__)
level = os.environ.get(f"LOG_LEVEL_{logger.name.upper()}")
if level:
    logger.setLevel(level.upper())
    logger.addHandler(logging.StreamHandler())
