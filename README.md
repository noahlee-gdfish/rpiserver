# rpiserver

## Python environment

- Need to use python virtual environment under ~/.env with the following packages installed

    Required packages : pyinstaller opencv-python opencv-contrib-python imutils dlib torch

## Components

- cameraserver is required at the same directory as rpiserver

    ```
    |- project_dir
        |- rpiserver
        |- cameraserver
    ```

    rpiserver/lib/camlib has symbolic link to ../../cameraserver

- build.sh is for personal use. Run build_rpiserver.sh to build binary
