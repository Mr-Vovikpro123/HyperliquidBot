import logging
from logging.handlers import RotatingFileHandler


log_path = 'py_log1.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.handlers.RotatingFileHandler(
    log_path, maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)