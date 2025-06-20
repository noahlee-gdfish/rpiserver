#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
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
from queue import Queue
from lib import sysmonitor, gpiomonitor, log_conf
from lib.camlib import cameraserver

#-- Items -----------------------------------------------------#
class eCommand(enum.Enum):
    CMD = 0             # User command
    FUNC = enum.auto()  # Function to run
    ARGS = enum.auto()  # Valid Args for the function if '[]', Number of args if integer, None if 'None', default variable if string
    STR = enum.auto()   # Usage string if FUNC!=None. Return string if FUNC==None

SOCKET_COMMAND_ARRAY = [
    [   "l", \
        "self.sysmon.ChangeLogLevel", \
        [1, 5], \
        "change log level\n\topt : none-next_level, 1-DEBUG, 2-INFO, 3-WARNING, 4-ERROR, 5-CRITICAL", \
    ], \
    [   "m", \
        "self.sysmon.ChangeMode", \
        [0, 1], \
        "change screen mode\n\topt : none-next_mode, 0-CLOCK, 1-INFO", \
    ], \
    [   "c", \
        "self.GetClients", \
        "client", \
        "Clients:", \
    ], \
    [   "chat", \
        "self.OpenChat", \
        1, \
        "openchat", \
    ], \
    [   "camera", \
        "self.sysmon.OpenRemoteCamera", \
        None, \
        "camera", \
    ], \
    [   "msg", \
        "self.sysmon.PrintMsg", \
        1, \
        "show message", \
    ], \
    [   "q", \
        None, \
        None, \
        "quit", \
    ], \
]
#--------------------------------------------------------------#

#-- Constants -------------------------------------------------#
HOST_IP_ADDR = subprocess.check_output("hostname -I", shell=True, encoding='utf-8').strip(' \n')
HOST_PORT_NUM = 9999
DATA_BUF_SIZE = 1024

CHATMSG_QUIT = "<quit>"
CHATMSG_WAITING_FOR_REMOTE = "<Waiting for remote>"
CHATMSG_REMOTE_CONNECTED = "<Remote connected>"

REMOTE_CLIENT_TIMEOUT = 0.5
#--------------------------------------------------------------#

#-- Items -----------------------------------------------------#
#--------------------------------------------------------------#
class RpiServer:
    def __init__(self):
        self.sysmon = sysmonitor.SystemMonitor(cameraserver)
        self.gpiomon = gpiomonitor.GpioMonitor(self, self.sysmon)
        self.exitevt = threading.Event()

        self.InitServerThread()
        self.InitSignals()
        self.InitServer()

        self.running = True

    def InitServerThread(self):
        self.mainthread = threading.Thread(target = self.ThreadMain, args = ())
        self.mainthread.daemon = True
        self.mainthread_running = True

    def InitSignals(self):
        signal.signal(signal.SIGINT, self.exit_signal_handler)
        signal.signal(signal.SIGTERM, self.exit_signal_handler)

    def InitServer(self):
        logger.info("Server start with ip : {0}".format(HOST_IP_ADDR))
        self.clients = []
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((HOST_IP_ADDR, HOST_PORT_NUM))
        self.server.listen()

    def exit_signal_handler(self, signum, frame):
        logger.debug("exit_signal_handler, signum {0}".format(signum))
        self.running = False
        self.mainthread_running = False
        self.exitevt.set()

    def ThreadMain(self):
        logger.debug("Start mainthread")

        try:
            while self.mainthread_running:
                logger.debug("Wait for client")

                client, addr = self.server.accept()
                clist = [client, addr]
                self.clients.append(clist)
                client.send("<connected>".encode())
                start_new_thread(self.ThreadClient, (clist,))
                self.sysmon.UpdateClient(True, addr) 

                logger.info("New client was added, total {0} clients".format(len(self.clients)))

        except Exception as e:
            logger.error("error : {0}".format(e))

        logger.debug("Exit mainthread")

    def ThreadClient(self, clist):
        client = clist[0]
        addr = [clist[1][0], clist[1][1]]
        logger.debug("Start clientthread for {0}:{1}".format(addr[0], addr[1]))

        while True:
            try:
                data = client.recv(DATA_BUF_SIZE)
                if not data:
                    logger.info("Disconnected by {0}:{1}".format(addr[0], addr[1]))
                    break

                logger.debug("Received from {0}:{1} << {2}".format(addr[0], addr[1], data.decode()))
                msg = self.ParseData(client, data.decode())

                response = "[{0}] {1}\n{2}".format(msg[2], msg[0], msg[1])
                client.send(response.encode())
                logger.debug("Send to {0}:{1} >> {2}".format(addr[0], addr[1], response))

            except ConnectionResetError as e:
                logger.info("Disconnected by {0}:{1}".format(addr[0], addr[1]))
                break

            except UnicodeDecodeError as e:
                logger.info("UnicodeDecodeError : {0}".format(e))
                continue

        if clist in self.clients:
            self.clients.remove(clist)
            self.sysmon.UpdateClient(False, addr) 
            logger.debug("Client was removed, total {0} clients".format(len(self.clients)))

        client.close()
        logger.debug("Exit clientthread {0}:{1}".format(addr[0], addr[1]))

    def OpenChat(self, arglist):
        to = arglist[0]
        addr = arglist[0].split(":")

        c = None
        for entry in self.clients:
            if "{0}:{1}".format(entry[1][0], entry[1][1]) == to:
                logger.debug("found {0}".format(to))
                c = entry[0]
                break

        if c == None:
            errmsg = "Client [{0}] is not available".format(to)
            logger.debug(errmsg)
            msg = [errmsg, "", "ERROR"]
            return msg

        start_new_thread(self.ThreadOpenChat, (to, c))

        msg = ["OpenChat", "{0} -- {1}".format(addr[0], addr[1]), "OK"]
        return msg


    def ThreadOpenChat(self, to, remote):
        q1 = Queue()
        q2 = Queue()
        evt1 = threading.Event()
        evt2 = threading.Event()

        client1_recv_q = Queue()
        client1_send_q = Queue()
        client2_recv_q = Queue()
        client2_send_q = Queue()
        client1_recv_evt = threading.Event()
        client1_send_evt = threading.Event()
        client2_recv_evt = threading.Event()
        client2_send_evt = threading.Event()

        logger.debug("initialize socksend")
        socksend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socksend.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socksend.bind((HOST_IP_ADDR, 10001))
        socksend.listen()

        logger.debug("initialize sockrecv")
        sockrecv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockrecv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockrecv.bind((HOST_IP_ADDR, 10002))
        sockrecv.listen()

        sockrecv1thread = threading.Thread(target = self.ThreadChatClientRecv, args = (sockrecv, q1, evt1, client1_recv_q, client1_recv_evt, q2, evt2))
        sockrecv1thread.deamon = True
        sockrecv1thread.start()

        socksend1thread = threading.Thread(target = self.ThreadChatClientSend, args = (socksend, q2, evt2, client1_send_q, client1_send_evt, q1, evt1))
        socksend1thread.deamon = True
        socksend1thread.start()

        client1_recv_evt.wait()
        client1_recv = client1_recv_q.get()
        client1_send_evt.wait()
        client1_send = client1_send_q.get()

        client1_send.send(CHATMSG_WAITING_FOR_REMOTE.encode())
        logger.debug("Client1 sockets are connected. Wait for client2")

        # check again
        client = None
        for entry in self.clients:
            if entry[0] == remote:
                client = remote
                break

        if client == None:
            errmsg = "Client [{0}] is not available".format(to)
            logger.debug(errmsg)
            client1_send.send("[ERROR] {0}".format(errmsg).encode())
            return

        client.send("OpenChatRequest".encode())

        sockrecv2thread = threading.Thread(target = self.ThreadChatClientRecv, args = (sockrecv, q2, evt2, client2_recv_q, client2_recv_evt, q1, evt1))
        sockrecv2thread.deamon = True
        sockrecv2thread.start()

        socksend2thread = threading.Thread(target = self.ThreadChatClientSend, args = (socksend, q1, evt1, client2_send_q, client2_send_evt, q2, evt2))
        socksend2thread.deamon = True
        socksend2thread.start()

        client2_recv_evt.wait()
        client2_recv = client2_recv_q.get()
        client2_send_evt.wait()
        client2_send = client2_send_q.get()
        if client2_recv == None or client2_send == None:
            logger.debug("Exit by Client1")
            return

        client1_send.send(CHATMSG_REMOTE_CONNECTED.encode())
        client2_send.send(CHATMSG_REMOTE_CONNECTED.encode())


    def ThreadChatClientSend(self, sock, q, evt, connected_q, connected_evt, recv_q, recv_evt):
        logger.debug("Start sendthread")

        while True:
            sock.settimeout(REMOTE_CLIENT_TIMEOUT)
            try:
                client, addr = sock.accept()
                break
            except socket.timeout:
                if q.empty():
                    continue
                elif q.get_nowait() == CHATMSG_QUIT:
                    recv_q.put(CHATMSG_QUIT)
                    connected_q.put(None)
                    connected_evt.set()
                    logger.debug("Exit sendthread, quit")
                    return
                else:
                    continue

        logger.debug("connected {0}:{1}".format(addr[0], addr[1]))
        connected_q.put(client)
        connected_evt.set()

        try:
            while True:
                evt.wait()
                chatstring = q.get()

                client.send(chatstring.encode())
                if chatstring == CHATMSG_QUIT:
                    break

                logger.debug("Send to {0}:{1} >> {2}".format(addr[0], addr[1], chatstring))

        except Exception as e:
            logger.error("error : {0}".format(e))

        logger.debug("Exit sendthread")
 
    def ThreadChatClientRecv(self, sock, q, evt, connected_q, connected_evt, send_q, send_evt):
        logger.debug("Start recvthread")

        while True:
            sock.settimeout(REMOTE_CLIENT_TIMEOUT)
            try:
                client, addr = sock.accept()
                break
            except socket.timeout:
                if q.empty():
                    continue
                elif q.get_nowait() == CHATMSG_QUIT:
                    connected_q.put(None)
                    connected_evt.set()
                    logger.debug("Exit recvthread, quit")
                    return
                else:
                    continue

        logger.debug("connected {0}:{1}".format(addr[0], addr[1]))
        connected_q.put(client)
        connected_evt.set()

        try:
            while True:
                data = client.recv(DATA_BUF_SIZE)
                if not data:
                    logger.info("Disconnected by {0}:{1}".format(addr[0], addr[1]))
                    break

                chatstring = data.decode()
                logger.debug("Received from {0}:{1} << {2}".format(addr[0], addr[1], chatstring))
                q.put(chatstring)
                evt.set()

        except Exception as e:
            logger.error("error : {0}".format(e))

        q.put(CHATMSG_QUIT)
        evt.set()
        send_q.put(CHATMSG_QUIT)
        send_evt.set()
        logger.debug("Exit recvthread")


    def IsValidArg(self, arglist, value):
        if value.isdigit():
            if int(value) >= arglist[0] and int(value) <= arglist[1]:
                return True

        return False

    def GetClients(self, client):
        msg = ["clients : ", "", "OK"]
        for clist in self.clients:
            if client == clist[0]:
                continue
            addr = [clist[1][0], clist[1][1]]
            msg[1] = msg[1]+"{0}:{1}\n".format(addr[0], addr[1])

        return msg

    def ParseArg(self, text):
        parsed = []
        temp = ""
        in_quotes = False

        for char in text:
            if char == "\"":
                in_quotes = not in_quotes
                if in_quotes:
                    temp = ""
                else:
                    parsed.append(temp)
                    temp = ""
                continue

            if not in_quotes:
                if char == " ":
                    if temp:
                        parsed.append(temp)
                        temp = ""
                    continue

            temp += char

        if temp:
            parsed.append(temp)

        return len(parsed), parsed

    def ParseData(self, client, data):
        argc, argv = self.ParseArg(data)
        item = None
        if argc > 0:
            for i, entry in enumerate(SOCKET_COMMAND_ARRAY):
                if entry[eCommand.CMD.value] == argv[0]:
                    item = entry
                    break

        if item == None:
            msg = ["Invalid command : {0}".format(argv[0]), "USAGE : ", "ERROR"]
            for i, item in enumerate(SOCKET_COMMAND_ARRAY):
                msg[1] = msg[1]+"\n - "+item[eCommand.CMD.value]
                if item[eCommand.ARGS.value]:
                    msg[1] = msg[1]+" [opt]"
                msg[1] = msg[1]+" : "+item[eCommand.STR.value]
            return msg

        if item[eCommand.FUNC.value] == None:
            msg = [item[eCommand.STR.value], "", "OK"]
        elif item[eCommand.ARGS.value] == None:
            msg = eval("{0}()".format(item[eCommand.FUNC.value]))
        elif str(type(item[eCommand.ARGS.value])) == "<class 'str'>":
            msg = eval("{0}({1})".format(item[eCommand.FUNC.value], item[eCommand.ARGS.value]))
        elif str(type(item[eCommand.ARGS.value])) == "<class 'list'>":
            if argc < 2:
                msg = eval("{0}()".format(item[eCommand.FUNC.value]))
            elif self.IsValidArg(item[eCommand.ARGS.value], argv[1]):
                msg = eval("{0}('{1}')".format(item[eCommand.FUNC.value], argv[1]))
            else:
                msg = ["Invalid argument '{0}' for '{1}'".format(argv[1], argv[0]), "", "ERROR"]
        else:
            if argc >= item[eCommand.ARGS.value]+1:
                del argv[0]
                msg = eval("{0}({1})".format(item[eCommand.FUNC.value], argv))
            else:
                msg = ["Need {0} arguments".format(item[eCommand.ARGS.value]), "", "ERROR"]

        return msg

    def Run(self):
        try:
            start_new_thread(self.sysmon.Run, ())
            start_new_thread(self.gpiomon.Run, ())
            start_new_thread(cameraserver.Run, ())
            self.mainthread.start()

            while self.running:
                self.exitevt.wait()

        except KeyboardInterrupt:
            logger.debug("KeyboardInterrupt")
            self.running = False
            self.mainthread_running = False
            self.exitevt.set()

    def Exit(self):
        self.sysmon.Exit()
        self.gpiomon.Exit()
        self.server.close()

def main(argc, argv):
    logger.info("rpiserver start")
    rpiserver = RpiServer()

    rpiserver.Run()
    logger.info("rpiserver exit")
    rpiserver.Exit()

if __name__ == '__main__':
    log_conf.init_logger()
    logger = logging.getLogger("rpiserver")
    main(len(sys.argv), sys.argv)


