"""Configuración de logging compartida (stdlib puro)."""

import logging
import sys


def get_logger(name: str = "astaroth", level: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        logger.addHandler(handler)

    if level:
        logger.setLevel(level)

    return logger
