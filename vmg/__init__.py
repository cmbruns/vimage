import logging
from .app import VimageApp

logging.basicConfig(level=logging.INFO)

# Instantiate top level app logger prior to stderr redirection tricks
logger = logging.getLogger(__name__)
