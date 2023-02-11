import asyncio
import io
import math
import os
import random
import threading
import time
from contextlib import contextmanager
from typing import List

import capnp
import numpy as np
import typer
import zmq.asyncio
from PIL import Image

from deepdrrzmq.zmqutil import zmq_no_linger_context
import cv2

from scipy.spatial.transform import Rotation as R



app = typer.Typer()

file_path = os.path.dirname(os.path.realpath(__file__))
messages = capnp.load(os.path.join(file_path, 'messages.capnp'))


@app.command()
def main(
        ip=typer.Argument('localhost', help="ip address of the server"),
        rep_port=typer.Argument(40100),
        pub_port=typer.Argument(40102),
        sub_port=typer.Argument(40101),
        # bind=typer.Option(True, help="bind to the port instead of connecting to it"),
):

    # print arguments
    print(f"req_port: {rep_port}")
    print(f"pub_port: {pub_port}")
    print(f"sub_port: {sub_port}")

    with zmq_no_linger_context(zmq.Context()) as context:
        req_socket = context.socket(zmq.REQ)
        req_socket.connect(f"tcp://{ip}:{rep_port}")

        pub_socket = context.socket(zmq.PUB)
        pub_socket.connect(f"tcp://{ip}:{pub_port}")

        sub_socket = context.socket(zmq.SUB)
        sub_socket.connect(f"tcp://{ip}:{sub_port}")

        sub_socket.setsockopt(zmq.SUBSCRIBE, b"")

        # request a new projector
        request = messages.ServerCommand.new_message()
        request.createProjector.projectorId = "test"
        request.createProjector.projectorParams.init("volumes", 1)
        request.createProjector.projectorParams.volumes[0].nifti.path = "~/datasets/DeepDRR_Data/CTPelvic1K_dataset6_CLINIC_0001/dataset6_CLINIC_0001_data.nii.gz"
        request.createProjector.projectorParams.volumes[0].nifti.useThresholding = True
        resolution = 500
        pixelSize = 1
        request.createProjector.projectorParams.device.camera.intrinsic.sensorWidth = resolution
        request.createProjector.projectorParams.device.camera.intrinsic.sensorHeight = resolution
        request.createProjector.projectorParams.device.camera.intrinsic.pixelSize = pixelSize
        request.createProjector.projectorParams.threads = 16
        request.createProjector.projectorParams.photonCount = 10
        request.createProjector.projectorParams.step = 2


        # send the request
        req_socket.send(request.to_bytes())
        print("sent request")

        # wait for the response
        print("waiting for response")
        response = req_socket.recv()
        print("received response")

        with messages.StatusResponse.from_bytes(response) as response:
            print(response)
            if response.code != 0:
                print("server returned error")
                return

        def requester():
            speed = 0.1
            scale = 30

            og_matrix = np.array(
                [[0, -1, 0, -1.95599373],
                [1, 0, 0, -1293.28274],
                [0, 0, 1, 829.996703],
                [0, 0, 0, 1]],
            )

            rotspeed = 2




            while True:
                project_request = messages.ProjectRequest.new_message()

                project_request.requestId = "asdf"
                project_request.projectorId = "test"
                project_request.init('cameraProjections', 1)
                project_request.cameraProjections[0].extrinsic.init('data', 16)

                matrix = og_matrix.copy()
                # matrix = np.eye(4)
                # matrix[1, 3] = 0
                # matrix[2, 3] = 0

                r = R.from_rotvec(time.time() * rotspeed * np.array([1, 0, 0]))

                # to homogeneous
                r_hom = np.eye(4)
                r_hom[:3, :3] = r.as_matrix()

                matrix =  matrix @ r_hom
                # matrix = r_hom @ matrix

                # matrix[1, 3] += math.sin(time.time() * speed * 2 * math.pi) * scale


                for i in range(16):
                    project_request.cameraProjections[0].extrinsic.data[i] = float(matrix[i // 4, i % 4])
                    project_request.cameraProjections[0].intrinsic.sensorWidth = resolution
                    project_request.cameraProjections[0].intrinsic.sensorHeight = resolution
                    project_request.cameraProjections[0].intrinsic.pixelSize = pixelSize

                pub_socket.send_multipart([b"project/", project_request.to_bytes()])

                # print(f"sending: {project_request}")
                time.sleep(0.01)

        # start the requester thread
        threading.Thread(target=requester, daemon=True).start()

        while True:
            # print("waiting for next image...")
            topic, data = sub_socket.recv_multipart()
            with messages.ProjectResponse.from_bytes(data) as response:
                # print(f"received image!")
                for img in response.images:
                    data = img.data
                    # read jpeg bytes
                    img = Image.open(io.BytesIO(data))
                    # print(img.size)
                    # show with opencv
                    cv2.imshow("image", np.array(img))
                    cv2.waitKey(1)







if __name__ == '__main__':
    try:
        app()
    except KeyboardInterrupt:
        pass
    print("Exiting...")
