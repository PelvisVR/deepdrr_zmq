import asyncio
import json
import os

import logging
from pathlib import Path
import numpy as np



import capnp
import deepdrr
import numpy as np
import typer
import zmq.asyncio

from deepdrrzmq.utils.zmq_util import zmq_no_linger_context

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
        sub_socket.hwm = 10000

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.setsockopt(zmq.SUBSCRIBE, b"patient_mesh_request/")
        sub_socket.setsockopt(zmq.SUBSCRIBE, b"patient_anno_request/")

        while True:
            try:
                latest_msgs = {}

                topic, data = await sub_socket.recv_multipart()
                latest_msgs[topic] = data

                # try:
                #     for i in range(1000):
                #         topic, data = await sub_socket.recv_multipart(flags=zmq.NOBLOCK)
                #         latest_msgs[topic] = data
                # except zmq.ZMQError:
                #     pass

                for topic, data in latest_msgs.items():
                    if topic == b"patient_mesh_request/":
                        await self.handle_patient_mesh_request(pub_socket, data)
                    elif topic == b"patient_anno_request/":
                        await self.handle_patient_annotation_request(pub_socket, data)

            except DeepDRRServerException as e:
                print(f"server exception: {e}")
                await pub_socket.send_multipart([b"server_exception/", e.status_response().to_bytes()])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    async def handle_patient_mesh_request(self, pub_socket, data):
        with messages.MeshRequest.from_bytes(data) as request:
            print(f"patient_mesh_request: {request.meshId}")

            meshId = request.meshId

            # open the mesh file
            mesh_file = self.patient_data_dir / meshId
            mesh = pv.read(mesh_file)

            msg = messages.MeshResponse.new_message()
            msg.meshId = meshId
            msg.status = make_response(0, "ok")
            msg.mesh.vertices = mesh.points.flatten().tolist()
            # todo: flip winding order on client side, not server
            msg.mesh.faces = mesh.faces.reshape((-1, 4))[..., 1:][..., [0, 2, 1]].flatten().tolist()

            response_topic = "patient_mesh_response/"+meshId

            await pub_socket.send_multipart([response_topic.encode(), msg.to_bytes()])
            print(f"sent mesh response {response_topic}")


    async def handle_patient_annotation_request(self, pub_socket, data):
        with messages.AnnoRequest.from_bytes(data) as request:
            print(f"patient_anno_request: {request.annoId}")

            annoId = request.annoId

            # open the annotation file
            annotation_file = self.patient_data_dir / annoId
            # parse json
            with open(annotation_file, "r") as f:
                annotation = json.load(f)

            controlPoints = annotation["markups"][0]["controlPoints"]


            msg = messages.AnnoResponse.new_message()
            msg.annoId = annoId
            msg.status = make_response(0, "ok")
            msg.anno.init("controlPoints", len(controlPoints))
            msg.anno.type = annotation["markups"][0]["type"]

            for i, controlPoint in enumerate(controlPoints):
                msg.anno.controlPoints[i].position.data = controlPoint["position"]

            response_topic = "patient_anno_response/"+annoId

            await pub_socket.send_multipart([response_topic.encode(), msg.to_bytes()])
            print(f"sent annotation response {response_topic}")
            

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

