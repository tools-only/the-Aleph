from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("aleph.service")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
