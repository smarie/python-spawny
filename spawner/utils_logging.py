# default logger
import logging
import sys

default_logger = logging.getLogger('spawner')
default_logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
default_logger.addHandler(ch)
# _default_logger.setLevel(logging.DEBUG)
