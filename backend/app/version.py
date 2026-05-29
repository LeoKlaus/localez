import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

_VALID_CHANNELS = {"stable", "beta", "preview"}


def _get_version() -> str:
    if v := os.environ.get("APP_VERSION"):
        return v
    try:
        return pkg_version("localez")
    except PackageNotFoundError:
        return "dev"


def _get_channel(version: str) -> str:
    c = os.environ.get("CHANNEL", "")
    if c in _VALID_CHANNELS:
        return c
    return "preview" if version.startswith("dev") else "stable"


__version__ = _get_version()
channel: str = _get_channel(__version__)
