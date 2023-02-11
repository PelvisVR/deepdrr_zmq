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


import capnp
import deepdrr
import numpy as np
import typer
import zmq.asyncio
from PIL import Image
from deepdrr import geo
from deepdrr.projector import Projector
from deepdrrzmq import timer_util

from deepdrrzmq.devices import SimpleDevice
from deepdrrzmq.zmqutil import zmq_no_linger_context

app = typer.Typer()

file_path = os.path.dirname(os.path.realpath(__file__))
messages = capnp.load(os.path.join(file_path, 'messages.capnp'))


def make_response(code, message):
    response = messages.StatusResponse.new_message()
    response.code = code
    response.message = message
    return response


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

    async def start(self):
        # control = self.control_server()
        project = self.project_server()
        await asyncio.gather(project)
        # await asyncio.gather(control, project)

    # async def control_server(self):
    #     rep_socket = self.context.socket(zmq.REP)
    #     rep_socket.hwm = 2

    #     rep_socket.bind(f"tcp://*:{self.rep_port}")

    #     while True:
    #         try:
    #             msg = await rep_socket.recv_multipart()
    #             print(f"received: {msg}")
                
    #         except DeepDRRServerException as e:
    #             await rep_socket.send_multipart([e.status_response().to_bytes()])
    #         except Exception as e:
    #             print(f"exception: {e}")
    #             await rep_socket.send_multipart([make_response(1, str(e)).to_bytes()])

    async def project_server(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 2

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 2

        pub_socket.bind(f"tcp://*:{self.pub_port}")
        sub_socket.bind(f"tcp://*:{self.sub_port}")

        sub_socket.setsockopt(zmq.SUBSCRIBE, b"")

        while True:
            try:
                topic, data = await sub_socket.recv_multipart()

                try:
                    for _ in range(100):
                        topic, data = await sub_socket.recv_multipart(flags=zmq.NOBLOCK)
                except zmq.ZMQError:
                    pass

                if topic == b"project_request/":
                    await self.handle_project_request(pub_socket, data)
                    if (f:=self.fps()) is not None:
                        print(f"FPS: {f:>5.2f}")
                elif topic == b"projector_params_response/":
                    await self.handle_projector_params_response(pub_socket, data)

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
        with messages.CreateProjectorRequest.from_bytes(data) as command:
            if self.projector_id == command.createProjector.projectorId:
                return

            projectorParams = command.createProjector.projectorParams

            self.volumes = []
            for volumeParams in projectorParams.volumes:
                if volumeParams.which() == "nifti":
                    niftiParams = volumeParams.nifti
                    niftiVolume = deepdrr.Volume.from_nifti(
                        path=str(Path(niftiParams.path).expanduser()),
                        world_from_anatomical=capnp_square_matrix(niftiParams.worldFromAnatomical),
                        use_thresholding=niftiParams.useThresholding,
                        use_cached=niftiParams.useCached,
                        save_cache=niftiParams.saveCache,
                        cache_dir=capnp_optional(niftiParams.cacheDir),
                        # materials=None,
                        segmentation=niftiParams.segmentation,
                        # density_kwargs=None,
                    )
                    niftiVolume.faceup()  # TODO: remove this
                    self.volumes.append(
                        niftiVolume
                    )
                else:
                    raise DeepDRRServerException(1, f"unknown volume type: {volumeParams.which()}")
            
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
            self.projector_id = command.createProjector.projectorId

            print(f"created projector: {projectorParams}")

    async def handle_project_request(self, pub_socket, data):
        with messages.ProjectRequest.from_bytes(data) as request:
            # print(f"received project request: {request}")
            if self.projector is None or request.projectorId != self.projector_id:
                msg = messages.ProjectorParamsRequest.new_message()
                msg.projectorId = request.projectorId
                await pub_socket.send_multipart([b"projector_params_request/", msg.to_bytes()])
                return

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
                pil_img = Image.fromarray((raw_image * 255).astype(np.uint8))
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG")

                msg.images[i].data = buffer.getvalue()

            await pub_socket.send_multipart([b"project_response/", msg.to_bytes()])
            # print(f"sent images response!")
    



@app.command()
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
    try:
        app()
    except KeyboardInterrupt:
        pass
    print("Exiting...")
