import os
import sys
import time
import threading
from _thread import *
import signal
import logging
import logging.config
import RPi.GPIO as GPIO

if getattr(sys, 'frozen', False):
    from lib import sysmonitor, log_conf
else:
    module_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_path)
    import sysmonitor, log_conf

GPIO_MODE_BUTTON = 26
GPIO_CLIENTS_BUTTON = 6
GPIO_LOGLEVEL_BUTTON = 16

class GpioMonitor:
    def __init__(self, rpiserver = None, sysmon = None):
        self._init_gpio()
        self.rpiserver = rpiserver
        self.sysmon = sysmon
        self.exitevt = threading.Event()

        self.running = True

    def _init_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_MODE_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(GPIO_MODE_BUTTON, GPIO.FALLING, callback=self.GpioIsrHandler, bouncetime=200)
        GPIO.setup(GPIO_CLIENTS_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(GPIO_CLIENTS_BUTTON, GPIO.FALLING, callback=self.GpioIsrHandler, bouncetime=200)
        GPIO.setup(GPIO_LOGLEVEL_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(GPIO_LOGLEVEL_BUTTON, GPIO.FALLING, callback=self.GpioIsrHandler, bouncetime=200)

    def InitMain(self):
        self.InitSignals()

    def GpioIsrHandler(self, channel):
        logger.debug("Key({0}) Pressed".format(channel))

        msg = None
        if channel == GPIO_MODE_BUTTON:
            msg = self.sysmon.ChangeMode()
        elif channel == GPIO_CLIENTS_BUTTON:
            if self.rpiserver == None:
                logger.debug("not supported in standalone mode")
            else:
                msg = self.sysmon.ShowClients(self.rpiserver.clients)
        elif channel == GPIO_LOGLEVEL_BUTTON:
            msg = self.sysmon.ShowLogLevel()

        if msg != None:
            logger.debug("[{0}] {1}\n{2}".format(msg[2], msg[0], msg[1]))

    def InitSignals(self):
        signal.signal(signal.SIGINT, self.exit_signal_handler)
        signal.signal(signal.SIGTERM, self.exit_signal_handler)

    def exit_signal_handler(self, signum, frame):
        logger.debug("exit_signal_handler, signum {0}".format(signum))
        self.running = False
        self.exitevt.set()

    def Run(self):
        while self.running:
            self.exitevt.wait()

    def Exit(self):
        #GPIO.cleanup()
        self.running = False
        self.exitevt.set()

def main(argc, argv):
    logger.info("gpiomonitor start")
    sysmon = sysmonitor.SystemMonitor()
    start_new_thread(sysmon.Run, ())
    gpiomon = GpioMonitor(sysmon = sysmon)
    gpiomon.InitMain()
    gpiomon.Run()

    logger.info("gpiomonitor exit")
    sysmon.Exit()
    gpiomon.Exit()

if __name__ == '__main__':
    log_conf.init_logger()
    logger = logging.getLogger("gpiomonitor")
    main(len(sys.argv), sys.argv)
else:
    logger = logging.getLogger("rpiserver")
