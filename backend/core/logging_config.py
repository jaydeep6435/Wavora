import logging.config
from typing import Any, Dict

def get_logging_config(environment: str = "development") -> Dict[str, Any]:
    """
    Returns a dictionary configuration for Python logging.
    In production, it can be extended to use JSON formatting for better log aggregation.
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "production": {
                "format": '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
                "datefmt": "%Y-%m-%dT%H:%M:%SZ",
            },
        },
        "handlers": {
            "console": {
                "formatter": "production" if environment == "production" else "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "wavora": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
    }
    return config

def setup_logging(environment: str = "development"):
    logging.config.dictConfig(get_logging_config(environment))
