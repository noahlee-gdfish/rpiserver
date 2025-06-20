import os
import sys
from picamera2 import Picamera2
import cv2
import numpy as np
import logging
import logging.config

class CvCamera():
    def __init__(self, width, height):
        self.cap = Picamera2()
        self.width = width
        self.height = height
        self.isopen = True

        try:
            logger.debug("{0}, {1}".format(width, height))
            self.config = self.cap.create_video_configuration(main={"format":"RGB888", "size":(width, height)})
            self.cap.align_configuration(self.config)
            self.cap.configure(self.config)
            self.cap.start()
        except:
            self.isopen = False
        return

    def read(self, dst=None):
        if dst is None:
            dst = np.empty((self.height, self.width, 3), dtype=np.uint8)
        if self.isopen:
            dst = self.cap.capture_array()
        return self.isopen, dst

    def isOpened(self):
        return self.isopen

    def release(self):
        if self.isopen:
            self.cap.close()
        self.isopen = False
        return

if __name__ == "__main__":
    import log_conf
    log_conf.init_logger()
    logger = logging.getLogger("cameraserver")

    camera = CvCamera(640, 480)

    while camera.isOpened():
        ret, frame = camera.read()
        if not ret:
            logger.debug("Empty Frame!!")
            continue
        cv2.imshow("CvCamera", frame)

        if cv2.waitKey(1) == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()
else:
    logger = logging.getLogger("cameraserver")
