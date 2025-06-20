import os
import sys
from flask import Flask, request, Response, stream_with_context, render_template_string
import logging
import logging.config
import cv2

if getattr(sys, 'frozen', False):
    from lib.camlib import streamer
else:
    module_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_path)
    import streamer, log_conf

app = Flask( __name__)
st = streamer.Streamer(width = 640, height = 480, mode = 0, stat = False)
clients = 0

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <title>Video Streaming</title>
    </head>
    <body>
    <meta charset="utf-8">
    <h1>와이프가 지켜보고있다!</h1>
    <img src="/stream" width="640" height="480">
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/stream')
def stream():
    try:
        return Response(
                                stream_with_context(stream_gen()),
                                mimetype='multipart/x-mixed-replace; boundary=frame' )
    except Exception as e:
        logger.error('stream error : ', str(e))

def stream_gen():
    global clients, st

    if clients == 0:
        st.run()
    clients += 1
    logger.info("stream connected, {0}".format(clients))

    while True:
        try:
            frame = cv2.imencode('.jpg', st.getimage())[1].tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except GeneratorExit:
            break

    clients -= 1
    logger.info("stream disconnected, {0}".format(clients))
    if clients == 0:
        st.stop()

def Run():
    app.run(host='0.0.0.0', port=8001)

if __name__ == '__main__':
    log_conf.init_logger()
    logger = logging.getLogger("cameraserver")
    Run()
else:
    logger = logging.getLogger("rpiserver")


