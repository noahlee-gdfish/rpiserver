#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
import io
import sys 
import time
import enum
import threading
import signal
import socket
import subprocess
from _thread import *
import logging
import logging.config
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
from camlib import streamer
import cv2

if getattr(sys, 'frozen', False):
    from lib import LCD_1inch69, log_conf
else:
    module_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_path)
    import LCD_1inch69, log_conf

#-- Enum ------------------------------------------------------#
class eColumn(enum.Enum):
    COMMAND = 0
    SYSCOMMAND = enum.auto()
    FORMAT = enum.auto()
    TYPE = enum.auto()
    SCALE = enum.auto()
    COLOR = enum.auto()
    X = enum.auto()
    Y = enum.auto()
    FONTSIZE = enum.auto()
    USAGE = enum.auto()

class eColumnMsg(enum.Enum):
    FORMAT = 0
    COLOR = enum.auto()
    X = enum.auto()
    Y = enum.auto()
    FONTSIZE = enum.auto()

class eMode(enum.Enum):
    CLOCK = 0
    INFO = enum.auto()
#--------------------------------------------------------------#

#-- Constants -------------------------------------------------#
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if getattr(sys, 'frozen', False):
    EXIT_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "pic/LCD_ExitImage.jpg")
else:
    EXIT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "pic/LCD_ExitImage.jpg")

IMAGE_ROTATE = 180

COLOR_BG = "BLACK"
REFRESH_TIME_SEC = 1
DEFAULT_MODECHANGE_TIME_SEC = 3
EXIT_IMAGE_TIME_SEC = 1
MSG_TIME_SEC = 1
#--------------------------------------------------------------#

#-- Items -----------------------------------------------------#
BAR_SIZE = 15
GAP_Y = 10
FONT_SIZE_SMALL, FONT_SIZE_LARGE = 18, 24
POS_X_DATE, POS_Y_DATE = 35, 5
POS_X_TIME, POS_Y_TIME = 70, POS_Y_DATE+FONT_SIZE_SMALL+5
POS_X_CLIENTS, POS_Y_CLIENTS = 20, POS_Y_TIME+FONT_SIZE_SMALL+5
POS_X_CPU, POS_Y_CPU = 1, 80
POS_X_MEM, POS_Y_MEM = 1, POS_Y_CPU+FONT_SIZE_LARGE+BAR_SIZE+GAP_Y
POS_X_TEMP, POS_Y_TEMP = 1, POS_Y_MEM+FONT_SIZE_LARGE+BAR_SIZE+GAP_Y
POS_X_FAN, POS_Y_FAN = 1, POS_Y_TEMP+FONT_SIZE_LARGE+BAR_SIZE+GAP_Y
# command       : system command to get result
# syscommand    : system command - True, internal variable - False
# format        : text format to print
# type          : type of value to print
# scale         : bar max of the value
# color         : text color to print
# x             : x pos of text
# y             : y pos of text
# fontsize      : font size of text
ITEM_ARRAY = [
            [   "date | awk '{printf(\"%s %s-%s %s\", $6, $3, $2, $1)}'", \
                True, \
                '{0}', \
                "str", 0, \
                "WHITE", POS_X_DATE, POS_Y_DATE, FONT_SIZE_SMALL, \
                '' \
            ],
            [   "date | awk '{printf(\"%s:%s\", $4, $5)}' | awk -F ':' '{printf(\"%s:%s %s\", $1, $2, $4)}'", \
                True, \
                '{0}', \
                "str", 0, \
                "WHITE", POS_X_TIME, POS_Y_TIME, FONT_SIZE_SMALL, \
                '' \
            ],
            [   "self.clients", \
                False, \
                '{0} clients connected', \
                "str", 0, \
                "LIGHTBLUE", POS_X_CLIENTS, POS_Y_CLIENTS, FONT_SIZE_SMALL, \
                '' \
            ],
            [   "vmstat --no-first | tail -1 | awk '{printf(\"%.1f\", 100 - $15)}'", \
                True, \
                'CPU: {0:0.1f}%', \
                "float", 100, \
                "YELLOW", POS_X_CPU, POS_Y_CPU, FONT_SIZE_LARGE, \
                '' \
            ],
            [   "top -bn1 | grep \"Mem :\" | awk '{printf(\"%.2f\", (1-(($6+$10)/$4))*100)}'", \
                True, \
                'MEM: {0:0.1f}%', \
                "float", 100, \
                "LIGHTCYAN", POS_X_MEM, POS_Y_MEM, FONT_SIZE_LARGE, \
                '' \
            ],
            [   "cat /sys/devices/virtual/thermal/thermal_zone0/temp | awk '{printf(\"%.2f\", $1/1000)}'", \
                True, \
                'TEMP: {0:0.1f}\u2103', \
                "float", 100, \
                "LIGHTBLUE", POS_X_TEMP, POS_Y_TEMP, FONT_SIZE_LARGE, \
                '' \
            ],
            [   "cat /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input", \
                True, \
                'FAN: {0}rpm', \
                "int", 10000, \
                "LIGHTGREEN", POS_X_FAN, POS_Y_FAN, FONT_SIZE_LARGE, \
                '' \
            ],
]

FONT_SIZE_CLOCK = 48
POS_X_CLOCK_DATE, POS_Y_CLOCK_DATE = 2, 80
POS_X_CLOCK_TIME, POS_Y_CLOCK_TIME = 2, POS_Y_CLOCK_DATE+FONT_SIZE_CLOCK+10
ITEM_CLOCK_ARRAY = [
            [   "date | awk '{printf(\"%s %s-%s %s\", $6, $3, $2, $1)}'", \
                True, \
                '{0}', \
                "str", 0, \
                "LIGHTGREEN", POS_X_CLOCK_DATE, POS_Y_CLOCK_DATE, FONT_SIZE_LARGE \
            ],
            [   "date | awk '{printf(\"%s\", $4)}'", \
                True, \
                '{0}', \
                "str", 0, \
                "WHITE", POS_X_CLOCK_TIME, POS_Y_CLOCK_TIME, FONT_SIZE_CLOCK \
            ],
]

FONT_SIZE_MSG_MSG, FONT_SIZE_MSG_INFO = FONT_SIZE_SMALL, FONT_SIZE_SMALL
POS_X_MSG_MSG, POS_Y_MSG_MSG = 2, 80
POS_X_MSG_INFO1, POS_Y_MSG_INFO1 = 2, POS_Y_MSG_MSG+FONT_SIZE_MSG_MSG+20
POS_X_MSG_INFO2, POS_Y_MSG_INFO2 = 2, POS_Y_MSG_INFO1+FONT_SIZE_MSG_INFO+10
# format    : text format to print
# color     : text color to print
# x         : x pos of text
# y         : y pos of text
# fontsize  : font size of text
ITEM_MSG_ARRAY = [
            [   "{0}", \
                "LIGHTBLUE", POS_X_MSG_MSG, POS_Y_MSG_MSG, FONT_SIZE_MSG_MSG \
            ],
            [   "{0}", \
                "WHITE", POS_X_MSG_INFO1, POS_Y_MSG_INFO1, FONT_SIZE_MSG_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_MSG_INFO2, POS_Y_MSG_INFO2, FONT_SIZE_MSG_INFO \
            ],
]

FONT_SIZE_CUSTOM_MSG, FONT_SIZE_CUSTOM_INFO = FONT_SIZE_SMALL, FONT_SIZE_SMALL
POS_X_CUSTOM_MSG, POS_Y_CUSTOM_MSG = 2, 15
POS_X_CUSTOM_INFO1, POS_Y_CUSTOM_INFO1 = 2, POS_Y_CUSTOM_MSG+FONT_SIZE_CUSTOM_MSG+20
POS_X_CUSTOM_INFO2, POS_Y_CUSTOM_INFO2 = 2, POS_Y_CUSTOM_INFO1+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO3, POS_Y_CUSTOM_INFO3 = 2, POS_Y_CUSTOM_INFO2+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO4, POS_Y_CUSTOM_INFO4 = 2, POS_Y_CUSTOM_INFO3+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO5, POS_Y_CUSTOM_INFO5 = 2, POS_Y_CUSTOM_INFO4+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO6, POS_Y_CUSTOM_INFO6 = 2, POS_Y_CUSTOM_INFO5+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO7, POS_Y_CUSTOM_INFO7 = 2, POS_Y_CUSTOM_INFO6+FONT_SIZE_CUSTOM_INFO+10
POS_X_CUSTOM_INFO8, POS_Y_CUSTOM_INFO8 = 2, POS_Y_CUSTOM_INFO7+FONT_SIZE_CUSTOM_INFO+10
# format    : text format to print
# color     : text color to print
# x         : x pos of text
# y         : y pos of text
# fontsize  : font size of text
ITEM_CUSTOM_ARRAY = [
            [   "{0}", \
                "LIGHTBLUE", POS_X_CUSTOM_MSG, POS_Y_CUSTOM_MSG, FONT_SIZE_CUSTOM_MSG \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO1, POS_Y_CUSTOM_INFO1, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO2, POS_Y_CUSTOM_INFO2, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO3, POS_Y_CUSTOM_INFO3, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO4, POS_Y_CUSTOM_INFO4, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO5, POS_Y_CUSTOM_INFO5, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO6, POS_Y_CUSTOM_INFO6, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO7, POS_Y_CUSTOM_INFO7, FONT_SIZE_CUSTOM_INFO \
            ],
            [   "{0}", \
                "WHITE", POS_X_CUSTOM_INFO8, POS_Y_CUSTOM_INFO8, FONT_SIZE_CUSTOM_INFO \
            ],
]
#--------------------------------------------------------------#

class SystemMonitor:
    def __init__(self):
        self.disp = self._init_display()
        self.font_small = ImageFont.truetype(FONT_PATH, FONT_SIZE_SMALL)
        self.font_large = ImageFont.truetype(FONT_PATH, FONT_SIZE_LARGE)
        self.font_clock = ImageFont.truetype(FONT_PATH, FONT_SIZE_CLOCK)
        self.mode = eMode.INFO.value
        self.automode = False
        self.msg_running = False
        self.modechange_interval = DEFAULT_MODECHANGE_TIME_SEC
        self.lock = threading.Lock()
        self.msglock = threading.Lock()

        self.clients = 0

        self.InitThreads()

        self.running = True

    def _init_display(self):
        try:
            disp = LCD_1inch69.LCD_1inch69()
            disp.Init()
            disp.clear()
            disp.bl_DutyCycle(100)
            return disp
        except IOError:
            sys.exit(1)

    def InitMain(self):
        self.InitSignals()
        self.automode = True

    def InitThreads(self):
        self.infothread = threading.Thread(target = self.Thread_GetInfo, args = (REFRESH_TIME_SEC,))
        self.infothread.daemon = True
        self.infothread_running = True

    def InitSignals(self):
        signal.signal(signal.SIGINT, self.exit_signal_handler)
        signal.signal(signal.SIGTERM, self.exit_signal_handler)

    def exit_signal_handler(self, signum, frame):
        logger.debug("exit_signal_handler, signum {0}".format(signum))
        self.running = False
        self.infothread_running = False

    def IsNumber(self, typestr):
        if typestr == "int": return True
        elif typestr == "float": return True
        else: return False

    def GetMode(self):
        self.lock.acquire()
        mode = self.mode
        self.lock.release()
        return mode

    def SetMode(self, mode):
        old_mode = self.GetMode()
        old_mode_str = str(eMode(old_mode)).lstrip('eMode.')
        mode_str = str(eMode(mode)).lstrip('eMode.')

        if old_mode == mode:
            logger.debug("Mode unchanged")
            return False
        else:
            self.lock.acquire()
            self.mode = mode
            self.lock.release()
            logger.debug("New mode {0}".format(mode_str))
            return True

    def ChangeMode(self, value=""):
        if value == "": # move to next mode
            mode = (self.GetMode()+1)%len(eMode)
        else:
            mode = int(value)

        ret = self.SetMode(mode)

        if ret:
            msg = ["Mode changed", "Current mode : {0}".format(str(eMode(self.GetMode())).lstrip('eMode.')), "OK"]
            start_new_thread(self.DrawMsg, ([msg[0], msg[1], ""],))
        else:
            msg = ["Mode unchanged", "Current mode : {0}".format(str(eMode(self.GetMode())).lstrip('eMode.')), "ERROR"]

        return msg

    def GetMsgRunning(self):
        self.msglock.acquire()
        msg_running = self.msg_running
        self.msglock.release()
        return msg_running

    def SetMsgRunning(self, msg_running):
        self.msglock.acquire()
        self.msg_running = msg_running
        self.msglock.release()

    def GetLogLevelStr(self, level):
        if level == 10:
            level_str = "DEBUG"
        elif level == 20:
            level_str = "INFO"
        elif level == 30:
            level_str = "WARNING"
        elif level == 40:
            level_str = "ERROR"
        elif level == 50:
            level_str = "CRITICAL"
        else:
            level_str = ""
        return level_str

    def ChangeLogLevel(self, value=""):
        old_level = logger.getEffectiveLevel()
        if value == "": # move to next level
            level = (old_level+10)%60
            if level == 0:
                level = 10
        else :
            level = int(value) * 10

        old_level_str = self.GetLogLevelStr(old_level)
        level_str = self.GetLogLevelStr(level)

        if old_level == level:
            msg = ["Log level unchanged", "Log level : {0}".format(level_str), "ERROR"]
            logger.critical(msg[1])
        else:
            logger.setLevel(level)
            msg = ["Log level changed", "Log level : {0}".format(level_str), "OK"]
            start_new_thread(self.DrawMsg, ([msg[0], msg[1], ""],))
            logger.critical("{0}, {1}".format(msg[0], msg[1]))

        return msg

    def PrintMsg(self, clientmsglist):
        msglist = []
        msglist.append("Client message")

        for msg in clientmsglist: 
            logger.debug(msg)
            msglist.append(msg)

        self.DrawCustomMsg(msglist)

        ret = ["Client message", str(clientmsglist), "OK"]
        return ret

    def UpdateClient(self, connected, addr):
        if connected:
            self.clients = self.clients +1
            msgstr = "New client connected"
        else:
            self.clients = self.clients -1
            msgstr = "Client disconnected"

        start_new_thread(self.DrawMsg, ([msgstr, "{0}:{1}".format(addr[0], addr[1]), ""],))

    def DrawBar(self, draw, xStart, yStart, xEnd, yEnd, color, percent):
        div = xStart+(xEnd-xStart)*percent/100
        draw.rectangle([(xStart, yStart), (xEnd, yEnd)], fill=COLOR_BG, outline=color)
        draw.rectangle([(xStart, yStart), (div, yEnd)], fill=color, outline=color)
        draw.rectangle([(div, yStart), (xEnd, yEnd)], fill=COLOR_BG, outline=color)

    def GetUsage(self, system_type, array):
        if array[system_type][eColumn.SYSCOMMAND.value]:
            usage = os.popen(array[system_type][eColumn.COMMAND.value]).read()
        else:
            usage = eval(array[system_type][eColumn.COMMAND.value])
        return usage

    def DrawInfo(self, draw):
        for i, item in enumerate(ITEM_ARRAY):
            self.lock.acquire()
            usage = item[eColumn.USAGE.value]
            self.lock.release()

            if usage == "":
                return

            if item[eColumn.FONTSIZE.value] == FONT_SIZE_SMALL :
                textfont = self.font_small
            else :
                textfont = self.font_large 

            color = item[eColumn.COLOR.value]
            if self.IsNumber(item[eColumn.TYPE.value]):
                percent = int(usage*100/item[eColumn.SCALE.value])
                if percent >= 90 :
                    color = "RED"

                self.DrawBar(draw, \
                            item[eColumn.X.value], \
                            item[eColumn.Y.value]+item[eColumn.FONTSIZE.value]+1, \
                            self.disp.width-1, \
                            item[eColumn.Y.value]+item[eColumn.FONTSIZE.value]+BAR_SIZE-1, \
                            color, \
                            percent)

            draw.text((item[eColumn.X.value], \
                        item[eColumn.Y.value]), \
                        item[eColumn.FORMAT.value].format(usage), \
                        fill=color, \
                        font=textfont)

    def DrawClock(self, draw):
        for i, item in enumerate(ITEM_CLOCK_ARRAY):
            usage = self.GetUsage(i, ITEM_CLOCK_ARRAY)

            if item[eColumn.FONTSIZE.value] == FONT_SIZE_SMALL :
                textfont = self.font_small
            elif item[eColumn.FONTSIZE.value] == FONT_SIZE_LARGE :
                textfont = self.font_large
            else :
                textfont = self.font_clock

            draw.text((item[eColumn.X.value], \
                        item[eColumn.Y.value]), \
                        item[eColumn.FORMAT.value].format(usage), \
                        fill=item[eColumn.COLOR.value], \
                        font=textfont)

    def DrawMsg(self, msglist):
        if self.automode:
            return

        if self.GetMsgRunning():
            self.msgtimer.cancel()

        self.SetMsgRunning(True)
        image = Image.new("RGB", (self.disp.width, self.disp.height), COLOR_BG)
        draw = ImageDraw.Draw(image)

        for i, item in enumerate(ITEM_MSG_ARRAY):
            if item[eColumnMsg.FONTSIZE.value] == FONT_SIZE_SMALL :
                textfont = self.font_small
            elif item[eColumnMsg.FONTSIZE.value] == FONT_SIZE_LARGE :
                textfont = self.font_large
            else :
                textfont = self.font_clock

            draw.text((item[eColumnMsg.X.value], \
                        item[eColumnMsg.Y.value]), \
                        item[eColumnMsg.FORMAT.value].format(msglist[i]), \
                        fill=item[eColumnMsg.COLOR.value], \
                        font=textfont)

        image=image.rotate(IMAGE_ROTATE)
        self.disp.ShowImage(image)

        self.msgtimer = threading.Timer(MSG_TIME_SEC, self.Timer_Msg)
        self.msgtimer.start()
        self.UpdateUsage()

    def DrawCustomMsg(self, msglist):
        if self.GetMsgRunning():
            self.msgtimer.cancel()

        self.SetMsgRunning(True)
        image = Image.new("RGB", (self.disp.width, self.disp.height), COLOR_BG)
        draw = ImageDraw.Draw(image)

        for i, item in enumerate(ITEM_CUSTOM_ARRAY):
            if item[eColumnMsg.FONTSIZE.value] == FONT_SIZE_SMALL :
                textfont = self.font_small
            elif item[eColumnMsg.FONTSIZE.value] == FONT_SIZE_LARGE :
                textfont = self.font_large
            else :
                textfont = self.font_clock

            draw.text((item[eColumnMsg.X.value], \
                        item[eColumnMsg.Y.value]), \
                        item[eColumnMsg.FORMAT.value].format(msglist[i]), \
                        fill=item[eColumnMsg.COLOR.value], \
                        font=textfont)

            if i >= len(msglist)-1:
                break

        image=image.rotate(IMAGE_ROTATE)
        self.disp.ShowImage(image)

        self.msgtimer = threading.Timer(MSG_TIME_SEC, self.Timer_Msg)
        self.msgtimer.start()

    def ShowClients(self, clients):
        msglist = []
        if len(clients) == 0:
            msglist.append("No clients")
        else: 
            msglist.append("Clients")

        retmsg = ""
        for clist in clients:
            if len(msglist) == len(ITEM_CUSTOM_ARRAY)-1:
                msglist.append("more clients...")
                retmsg = retmsg+"\nmore clients..."
                break

            msglist.append("{0}:{1}".format(clist[1][0], clist[1][1]))
            retmsg = retmsg+"{0}:{1}\n".format(clist[1][0], clist[1][1])

        self.DrawCustomMsg(msglist)

        ret = [msglist[0], retmsg, "OK"]
        return ret

    def ShowLogLevel(self):
        level = logger.getEffectiveLevel()
        level_str = self.GetLogLevelStr(level)

        msglist = []
        msglist.append("Current Log level")
        msglist.append(level_str)
        self.DrawCustomMsg(msglist)

        msg = ["Current Log level", level_str, "OK"]
        return msg

    def DrawExitImage(self):
        image = Image.open(EXIT_IMAGE_PATH)
        image = image.rotate(IMAGE_ROTATE)
        self.disp.ShowImage(image)

    def Timer_Msg(self):
        self.SetMsgRunning(False)

    def UpdateUsage(self):
        for i, item in enumerate(ITEM_ARRAY):
            usage = self.GetUsage(i, ITEM_ARRAY)

            if item[eColumn.TYPE.value] == "float" and usage != '':
                usage = float(usage)
            elif item[eColumn.TYPE.value] == "int" and usage != '':
                usage = int(usage)

            self.lock.acquire()
            item[eColumn.USAGE.value] = usage
            self.lock.release()

    def Thread_GetInfo(self, interval):
        logger.debug("Start infothread")

        while self.infothread_running:
            self.UpdateUsage()
            time.sleep(interval)

        logger.debug("Exit infothread")

    def Run(self):
        image = Image.new("RGB", (self.disp.width, self.disp.height), COLOR_BG)
        draw = ImageDraw.Draw(image)

        global st
        st.run()
        while self.running:
            try:
                frame = st.getimage()
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image = image.rotate(IMAGE_ROTATE)
                self.disp.ShowImage(image)

            except KeyboardInterrupt:
                logger.debug("KeyboardInterrupt")
                self.running = False

        st.stop()


    def Exit(self):
        self.running = False
        self.infothread_running = False

        if self.infothread.is_alive():
            logger.debug("Wait for threads to exit")
            self.infothread.join()
        logger.debug("DrawExitImage")
        self.DrawExitImage()
        time.sleep(EXIT_IMAGE_TIME_SEC)

        logger.debug("Reset display")
        self.disp.reset()
        self.disp.module_exit()



def main(argc, argv):
    logger.info("sysmonitor start")
    sysmon = SystemMonitor()
    sysmon.InitMain()

    if argc >= 2:
        self.modechange_interval = int(argv[1])
    logger.info("mode change interval {0} seconds".format(sysmon.modechange_interval))
    global st
    st = streamer.Streamer(width = 240, height = 225, mode = 0, stat = False)
    sysmon.Run()

    logger.info("sysmonitor exit")
    sysmon.Exit()

if __name__ == '__main__':
    log_conf.init_logger()
    logger = logging.getLogger("systemmonitor")
    main(len(sys.argv), sys.argv)
else:
    logger = logging.getLogger("rpiserver")


