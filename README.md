# rpiserver

## Python environment

0. Need to use python virtual environment under ~/.env with the following packages installed

    Required packages : pyinstaller opencv-python opencv-contrib-python imutils dlib torch

1. cameraserver is required at the same directory as rpiserver

    ```
    |- project_dir
        |- rpiserver
        |- cameraserver
    ```

    rpiserver/lib/camlib has symbolic link to ../../cameraserver
