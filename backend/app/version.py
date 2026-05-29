import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version


def _get_version() -> str:
    if v := os.environ.get("APP_VERSION"):
        return v
    try:
        return pkg_version("localez")
    except PackageNotFoundError:
        return "dev"


__version__ = _get_version()
channel: str = "preview" if __version__.startswith("dev") else "stable"
