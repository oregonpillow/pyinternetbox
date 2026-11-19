from importlib.metadata import PackageNotFoundError, version

from internetbox_client.client import InternetBoxClient
from internetbox_client.utils.APIClient import APIClient, SessionManager

try:
    __version__ = version("pyinternetbox")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"

PROJECT_NAME = "pyinternetbox"
PROJECT_URL = "https://github.com/oregonpillow/pyinternetbox"

__all__ = ["PROJECT_NAME", "PROJECT_URL", "APIClient", "InternetBoxClient", "SessionManager", "__version__"]
