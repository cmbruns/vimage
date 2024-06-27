import logging
from .app import VimageApp

# Create top level logger before invoking VimageApp
logging.basicConfig(level=logging.DEBUG,)
logger = logging.getLogger(__name__)
