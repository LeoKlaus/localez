import logging.config

from app.config import settings


def configure_logging() -> None:
    level = settings.log_level.upper()

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
        "loggers": {
            # uvicorn manages its own loggers — let them propagate to root
            "uvicorn": {"propagate": True},
            "uvicorn.access": {"propagate": True},
            # SQLAlchemy is extremely noisy at DEBUG; keep it quiet unless explicitly raised
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        },
    })
