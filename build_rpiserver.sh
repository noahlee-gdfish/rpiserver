#!/bin/bash

source ~/.env/bin/activate
pyinstaller -F rpiserver.py --hidden-import gpiozero.pins.lgpio --hidden-import imutils --hidden-import dlib --hidden-import torch --add-data="./lib/camlib/xml/haarcascade_frontalface_default.xml:." --add-data="./lib/camlib/xml/haarcascade_eye.xml:." --add-data="./lib/pic/LCD_ExitImage.jpg:."
deactivate
cp ./dist/rpiserver .
