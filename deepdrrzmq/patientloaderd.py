import asyncio
import io
import os
from contextlib import contextmanager
from typing import List

import deepdrr
from deepdrr import geo
from deepdrr.utils import test_utils, image_utils
from deepdrr.projector import Projector
from PIL import Image
import logging
from pathlib import Path
import numpy as np

import time


import capnp
import deepdrr
import numpy as np
import typer
import zmq.asyncio
from PIL import Image
from deepdrr import geo
from deepdrr.projector import Projector
from deepdrrzmq.utils import timer_util

from deepdrrzmq.devices import SimpleDevice
from deepdrrzmq.utils.zmq_util import zmq_no_linger_context

from .utils.drr_util import from_nifti_cached, from_meshes_cached
from .utils.typer_util import unwrap_typer_param

from .deepdrrd import DeepDRRServerException

import pyvista as pv

# app = typer.Typer()
app = typer.Typer(pretty_exceptions_show_locals=False)

file_path = os.path.dirname(os.path.realpath(__file__))
messages = capnp.load(os.path.join(file_path, 'messages.capnp'))


def make_response(code, message):
    response = messages.StatusResponse.new_message()
    response.code = code
    response.message = message
    return response


def capnp_optional(optional):
    if optional.which() == "value":
        return optional.value
    else:
        return None

def capnp_square_matrix(optional):
    if len(optional.data) == 0:
        return None
    else:
        arr = np.array(optional.data)
        size = len(arr)
        side = int(size ** 0.5)
        assert size == side ** 2, f"expected square matrix, got {size} elements"
        arr = arr.reshape((side, side))
        return arr

class PatientLoaderServer:
    def __init__(self, context, rep_port, pub_port, sub_port):
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port

        # PATIENT_DATA_DIR environment variable is set by the docker container
        default_data_dir = Path("/mnt/d/jhonedrive/Johns Hopkins/Benjamin D. Killeen - NMDID-ARCADE/")  # TODO: remove
        self.patient_data_dir = Path(os.environ.get("PATIENT_DATA_DIR", default_data_dir))

        logging.info(f"patient data dir: {self.patient_data_dir}")

    async def start(self):
        project = self.project_server()
        await asyncio.gather(project)

    async def project_server(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 2

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 2

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.setsockopt(zmq.SUBSCRIBE, b"patient_mesh_request/")

        while True:
            try:
                latest_msgs = {}

                topic, data = await sub_socket.recv_multipart()
                latest_msgs[topic] = data

                try:
                    for i in range(1000):
                        topic, data = await sub_socket.recv_multipart(flags=zmq.NOBLOCK)
                        latest_msgs[topic] = data
                except zmq.ZMQError:
                    pass

                for topic, data in latest_msgs.items():
                    if topic == b"patient_mesh_request/":
                        await self.handle_patient_mesh_request(pub_socket, data)

            except DeepDRRServerException as e:
                print(f"server exception: {e}")
                await pub_socket.send_multipart([b"server_exception/", e.status_response().to_bytes()])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.projector is not None:
            self.projector.__exit__(exc_type, exc_value, traceback)

    async def handle_patient_mesh_request(self, pub_socket, data):
        with messages.MeshRequest.from_bytes(data) as request:

            meshId = request.meshId

            # open the mesh file
            mesh_file = self.patient_data_dir / meshId
            mesh = pv.read(mesh_file)

            msg = messages.MeshResponse.new_message()
            msg.meshId = meshId
            msg.status = make_response(0, "ok")
            msg.mesh.vertices = mesh.points.flatten().tolist()
            msg.mesh.faces = mesh.faces.flatten().tolist()

            await pub_socket.send_multipart([b"patient_mesh_response/", msg.to_bytes()])


@app.command()
@unwrap_typer_param
def main(
        # ip=typer.Argument('localhost', help="ip address of the receiver"),
        rep_port=typer.Argument(40100),
        pub_port=typer.Argument(40101),
        sub_port=typer.Argument(40102),
        # bind=typer.Option(True, help="bind to the port instead of connecting to it"),
):

    # print arguments
    print(f"rep_port: {rep_port}")
    print(f"pub_port: {pub_port}")
    print(f"sub_port: {sub_port}")

    with zmq_no_linger_context(zmq.asyncio.Context()) as context:
        with PatientLoaderServer(context, rep_port, pub_port, sub_port) as patient_loader_server:
            asyncio.run(patient_loader_server.start())


if __name__ == '__main__':
    app()

