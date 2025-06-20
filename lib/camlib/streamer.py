import os
import sys
import time
import cv2
import imutils
import platform
import numpy as np
from threading import Thread
from queue import Queue
import logging
import logging.config

if getattr(sys, 'frozen', False):
    from lib.camlib import cvcamera, cameramode
else:
    module_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_path)
    import cvcamera, cameramode

class Streamer:
    def __init__(self, width = 640, height = 480, mode = 0, stat = False):
        self.capture = None
        self.thread = None
        self.width = width
        self.height = height
        self.stat = stat
        self.mode = mode
        self.preview_time = time.time()
        self.sec = 0
        self.Q = Queue(maxsize=128)
        self.started = False

    def run(self):
        if self.started:
            return

        logger.info("run")
        self.capture = cvcamera.CvCamera(self.width, self.height)
        self.started = True

        self.thread = Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info("stop")
        self.started = False

        if self.capture is not None:
            self.capture.release()
            self.clear()

    def update(self):
        while self.started:
            (grabbed, frame) = self.capture.read()
 
            if grabbed:
                if self.stat:
                    frame, self.preview_time = cameramode.addfps(frame, self.preview_time)
                frame = cameramode.applymode(frame, self.mode)
                self.clear()
                self.Q.put(frame)

    def clear(self):
        with self.Q.mutex:
            self.Q.queue.clear()

    def read(self):
        return self.Q.get()

    def blank(self):
        return np.ones(shape=[self.height, self.width, 3], dtype=np.uint8)

    def getimage(self):
        if not self.capture.isOpened():
            frame = self.blank()
        else:
            frame = imutils.resize(self.read(), width=int(self.width))

        return frame

    def __exit__(self):
        self.capture.release()

if __name__ == '__main__':
    import log_conf
    log_conf.init_logger()
    logger = logging.getLogger("cameraserver")
else:
    logger = logging.getLogger("cameraserver")
