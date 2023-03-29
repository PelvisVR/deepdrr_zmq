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

def mesh_msg_to_volume(meshParams):
    surfaces = []
    for volumeMesh in meshParams.meshes:
        vertices = np.array(volumeMesh.mesh.vertices).reshape(-1, 3)
        faces = np.array(volumeMesh.mesh.faces).reshape(-1, 3)
        faces = np.pad(faces, ((0, 0), (1, 0)), constant_values=3)
        faces = faces.flatten()
        if len(faces) == 0:
            continue
        surface = pv.PolyData(vertices, faces)
        surfaces.append((volumeMesh.material, volumeMesh.density, surface))

    meshVolume = from_meshes_cached(
        voxel_size=meshParams.voxelSize,
        surfaces=surfaces
    )
    return meshVolume

def nifti_msg_to_volume(niftiParams, patient_data_dir):
    # if niftiParams.path is a relative path, make it relative to the patient data directory
    if not Path(niftiParams.path).expanduser().is_absolute():
        niftiPath = str(patient_data_dir / niftiParams.path)
    else:
        niftiPath = niftiParams.path

    niftiVolume = from_nifti_cached(
        path=niftiPath,
        world_from_anatomical=capnp_square_matrix(niftiParams.worldFromAnatomical),
        use_thresholding=niftiParams.useThresholding,
        use_cached=niftiParams.useCached,
        save_cache=niftiParams.saveCache,
        cache_dir=capnp_optional(niftiParams.cacheDir),
        # materials=None,
        segmentation=niftiParams.segmentation,
        # density_kwargs=None,
    )
    return niftiVolume

class DeepDRRServerException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return f"DeepDRRServerError({self.code}, {self.message})"

    def status_response(self):
        return make_response(self.code, self.message)

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

class DeepDRRServer:
    def __init__(self, context, rep_port, pub_port, sub_port):
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port

        self.projector = None
        self.projector_id = ""

        self.volumes = []  # type: List[deepdrr.Volume]

        self.fps = timer_util.FPS(1)
        
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

        sub_socket.setsockopt(zmq.SUBSCRIBE, b"project_request/")
        sub_socket.setsockopt(zmq.SUBSCRIBE, b"projector_params_response/")

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
                    if topic == b"project_request/":
                        if await self.handle_project_request(pub_socket, data):
                            if (f:=self.fps()) is not None:
                                print(f"DRR project rate: {f:>5.2f} frames per second")
                    elif topic == b"projector_params_response/":
                        await self.handle_projector_params_response(data)

            except DeepDRRServerException as e:
                print(f"server exception: {e}")
                await pub_socket.send_multipart([b"server_exception/", e.status_response().to_bytes()])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.projector is not None:
            self.projector.__exit__(exc_type, exc_value, traceback)

    async def handle_projector_params_response(self, data):
        # for now, only one projector at a time
        # if the current projector is not the same as the one in the request, delete the old and create a new one
        with messages.ProjectorParamsResponse.from_bytes(data) as command:
            if self.projector_id == command.projectorId:
                return

            print(f"creating projector {command.projectorId}")

            projectorParams = command.projectorParams

            self.volumes = []
            for volumeParams in projectorParams.volumes:
                print(f"adding {volumeParams.which()} volume")
                if volumeParams.which() == "nifti":
                    self.volumes.append(nifti_msg_to_volume(volumeParams.nifti, self.patient_data_dir))
                elif volumeParams.which() == "mesh":
                    self.volumes.append(mesh_msg_to_volume(volumeParams.mesh))
                elif volumeParams.which() == "instrument":
                    raise DeepDRRServerException(1, f"Instruments deprecated, use meshes instead")
                else:
                    raise DeepDRRServerException(1, f"unknown volume type: {volumeParams.which()}")
            
            print(f"creating projector")
            deviceParams = projectorParams.device
            device = SimpleDevice(
                sensor_height=deviceParams.camera.intrinsic.sensorHeight,
                sensor_width=deviceParams.camera.intrinsic.sensorWidth,
                pixel_size=deviceParams.camera.intrinsic.pixelSize,
                source_to_detector_distance=deviceParams.camera.intrinsic.sourceToDetectorDistance,
                world_from_device=geo.frame_transform(capnp_square_matrix(deviceParams.camera.extrinsic)),
            )

            if self.projector is not None:
                self.projector.__exit__(None, None, None)
                self.projector = None
                self.projector_id = ""

            self.projector = Projector(
                volume=self.volumes,
                device=device,
                step=projectorParams.step,
                mode=projectorParams.mode,
                spectrum=projectorParams.spectrum,
                scatter_num=projectorParams.scatterNum,
                add_noise=projectorParams.addNoise,
                photon_count=projectorParams.photonCount,
                threads=projectorParams.threads,
                max_block_index=projectorParams.maxBlockIndex,
                collected_energy=projectorParams.collectedEnergy,
                neglog=projectorParams.neglog,
                intensity_upper_bound=capnp_optional(projectorParams.intensityUpperBound),
                attenuate_outside_volume=projectorParams.attenuateOutsideVolume,
            )
            self.projector.__enter__()
            self.projector_id = command.projectorId

            print(f"created projector {self.projector_id}")

    async def handle_project_request(self, pub_socket, data):
        with messages.ProjectRequest.from_bytes(data) as request:
            # print(f"received project request: {request.requestId} for projector {request.projectorId}")
            if self.projector is None or request.projectorId != self.projector_id:
                msg = messages.ProjectResponse.new_message()
                msg.requestId = request.requestId
                msg.projectorId = request.projectorId
                msg.status = make_response(0, "ok")

                msg.init("images", 1)

                green_loading_img = np.zeros((512, 512, 3), dtype=np.uint8)
                green_loading_img[:, :, 1] = 255
                pil_img = Image.fromarray(green_loading_img)
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG")
                msg.images[0].data = buffer.getvalue()
                await pub_socket.send_multipart([b"project_response/", msg.to_bytes()])


                msg = messages.ProjectorParamsRequest.new_message()
                msg.projectorId = request.projectorId
                await pub_socket.send_multipart([b"projector_params_request/", msg.to_bytes()])
                print(f"projector {request.projectorId} not found, requesting projector params")
                return False

            camera_projections = []
            for camera_projection_struct in request.cameraProjections:
                camera_projections.append(
                    geo.CameraProjection(
                        intrinsic=geo.CameraIntrinsicTransform.from_sizes(
                            sensor_size=(camera_projection_struct.intrinsic.sensorWidth, camera_projection_struct.intrinsic.sensorHeight),
                            pixel_size=camera_projection_struct.intrinsic.pixelSize,
                            source_to_detector_distance=camera_projection_struct.intrinsic.sourceToDetectorDistance,
                        ),
                        extrinsic=geo.frame_transform(capnp_square_matrix(camera_projection_struct.extrinsic))
                    )
                )

            volumes_world_from_anatomical = []
            for transform in request.volumesWorldFromAnatomical:
                volumes_world_from_anatomical.append(
                    geo.frame_transform(capnp_square_matrix(transform))
                )

            if len(volumes_world_from_anatomical) == 0:
                pass  # all volumes are static
            elif len(volumes_world_from_anatomical) == len(self.volumes):
                for volume, transform in zip(self.volumes, volumes_world_from_anatomical):
                    volume.world_from_anatomical = transform
            else:
                raise DeepDRRServerException(3, "volumes_world_from_anatomical length mismatch")

            raw_images = self.projector.project(
                *camera_projections,
            )

            if len(camera_projections) == 1:
                raw_images = [raw_images]

            msg = messages.ProjectResponse.new_message()
            msg.requestId = request.requestId
            msg.projectorId = request.projectorId
            msg.status = make_response(0, "ok")

            msg.init("images", len(raw_images))

            for i, raw_image in enumerate(raw_images):
                # use jpeg compression
                pil_img = Image.fromarray(((1-raw_image) * 255).astype(np.uint8))
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG")

                msg.images[i].data = buffer.getvalue()

            await pub_socket.send_multipart([b"project_response/", msg.to_bytes()])

            return True
    


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
        with DeepDRRServer(context, rep_port, pub_port, sub_port) as deepdrr_server:
            asyncio.run(deepdrr_server.start())


if __name__ == '__main__':
    app()

