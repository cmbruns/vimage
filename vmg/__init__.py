import logging
from .app import VimageApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d[%(levelname)-.1s]%(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Instantiate top level app logger prior to stderr redirection tricks
logger = logging.getLogger(__name__)
logger.info("Loading vmg module")
