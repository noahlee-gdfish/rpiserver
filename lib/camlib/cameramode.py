import cv2
import os
import sys
import dlib
import torch
import time

def mode_cascade(frame):
    if getattr(sys, 'frozen', False):
        xml_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "camlib/xml/")
    else:
        xml_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "xml/")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    #eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    face_cascade = cv2.CascadeClassifier(xml_path + "haarcascade_frontalface_default.xml")
    eye_cascade = cv2.CascadeClassifier(xml_path + "haarcascade_eye.xml")
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

        roi_gray = gray[y:y+h, x:x+w]
        roi_color = frame[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.3, minNeighbors=5)

        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 2)

    return frame

def mode_dlib(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces_hog = dlib.get_frontal_face_detector()
    faces = faces_hog(gray, 1)

    for face in faces:
        cv2.rectangle(frame, (face.left(), face.top()), (face.right(), face.bottom()), (255, 0, 0), 2)

    return frame

def mode_yolov(image):
    model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
    results = model(image)
    frame = results.render()[0]

    return frame

def applymode(frame, mode):
    if mode == 1:
        frame = mode_cascade(frame)
    elif mode == 2:
        frame = mode_dlib(frame)
    elif mode == 3:
        frame = mode_yolov(frame)

    return frame

def fps(preview_time):
        current_time = time.time()
        sec = current_time - preview_time
        preview_time = current_time

        if sec > 0:
            fpsnum = round(1/(sec),1)
        else:
            fpsnum = 1

        return fpsnum, preview_time


def addfps(frame, ptime):
    cv2.rectangle(frame, (0,0), (120,30), (0,0,0), -1)
    fpsnum, ptime = fps(ptime)
    fpstext = 'FPS : ' + str(fpsnum)
    cv2.putText(frame, fpstext, (10,20), cv2.FONT_HERSHEY_PLAIN, 1, (0,0,255), 1, cv2.LINE_AA)

    return frame, ptime

