#!/usr/bin/python

import os
import sys
import logging
import logging.config

def init_logger():
    if getattr(sys, 'frozen', False):
        config_file = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "config/cameraserver_log.config")
    else:
        config_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "config/cameraserver_log.config")

    logging.config.fileConfig(config_file)
    logger = logging.getLogger("cameraserver")
    loglevel = 0

