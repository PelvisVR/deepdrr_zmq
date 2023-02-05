import asyncio
import io
import os
from contextlib import contextmanager
from typing import List

import capnp
import numpy as np
import typer
import zmq.asyncio
from PIL import Image

from deepdrrzmq.zmqutil import zmq_no_linger_context

app = typer.Typer()


file_path = os.path.dirname(os.path.realpath(__file__))
messages = capnp.load(os.path.join(file_path, 'messages.capnp'))

# struct NiftiLoaderParams {
#     path @0 :Text;
#     worldFromAnatomical @1 :Matrix4x4;
#     useThresholding @2 :Bool;
#     useCached @3 :Bool;
#     saveCache @4 :Bool;
#     cacheDir @5 :Text;
# #   materials @? :List(Text);
#     segmentation @6 :Bool;
# #    densityKwargs @? :List(Text);
# }
#
# struct DicomLoaderParams { # todo
#     path @0 :Text;
#     worldFromAnatomical @1 :Matrix4x4;
#     useThresholding @2 :Bool;
#     useCached @3 :Bool;
#     saveCache @4 :Bool;
#     cacheDir @5 :Text;
# #   materials @? :List(Text);
#     segmentation @6 :Bool;
# #    densityKwargs @? :List(Text);
# }
#
# struct VolumeLoaderParams {
#     union {
#         nifti @0 :NiftiLoaderParams;
#         dicom @1 :DicomLoaderParams;
#     }
# }
#
# struct ProjectorParams {
#     volumes @0 :List(VolumeLoaderParams);
#     step @1 :Float32;
#     mode @2 :Text;
#     spectrum @3 :Text;
#     addScatter @4 :Bool;
#     scatterNum @5 :UInt32;
#     addNoise @6 :Bool;
#     photonCount @7 :UInt32;
#     threads @8 :UInt32;
#     maxBlockIndex @9 :UInt32;
#     collectedEnergy @10 :Bool;
#     neglog @11 :Bool;
#     intensityUpperBound @12 :Float32;
#     attenuateOutsideVolume @13 :Bool;
# }
#
# struct CreateProjectorRequest {
#     projectorId @0 :Text;
#     projectorParams @1 :ProjectorParams;
# }
#
# struct DeleteProjectorRequest {
#     projectorId @0 :Text;
# }
#
# struct ServerCommand {
#     union {
#         createProjector @0 :CreateProjectorRequest;
#         deleteProjector @1 :DeleteProjectorRequest;
#     }
# }


@app.command()
def main(
        ip=typer.Argument('localhost', help="ip address of the server"),
        rep_port=typer.Argument(40000),
        pub_port=typer.Argument(40001),
        sub_port=typer.Argument(40002),
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
        request.createProjector.projectorParams.volumes[0].nifti.path = "/home/wangl/datasets/DeepDRR_Data/CTPelvic1K_dataset6_CLINIC_0001/dataset6_CLINIC_0001_data.nii.gz"
        request.createProjector.projectorParams.volumes[0].nifti.useThresholding = True

        # send the request
        req_socket.send(request.to_bytes())
        print("sent request")

        # wait for the response
        print("waiting for response")
        response = req_socket.recv()
        print("received response")

        with messages.StatusResponse.from_bytes(response) as response:
            print(response)






if __name__ == '__main__':
    try:
        app()
    except KeyboardInterrupt:
        pass
    print("Exiting...")
