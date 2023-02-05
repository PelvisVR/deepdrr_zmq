from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from deepdrr import geo
from deepdrr.device import Device

class SimpleDevice(Device):
    sensor_height: int
    sensor_width: int
    pixel_size: float

    camera_intrinsics: geo.CameraIntrinsicTransform
    source_to_detector_distance: float
    world_from_device: geo.FrameTransform

    def __init__(self, sensor_height: int, sensor_width: int, pixel_size: float, source_to_detector_distance: float, world_from_device: geo.FrameTransform):
        self.sensor_height = sensor_height
        self.sensor_width = sensor_width
        self.pixel_size = pixel_size
        self.source_to_detector_distance = source_to_detector_distance
        self.world_from_device = world_from_device
        self.camera_intrinsics = geo.CameraIntrinsicTransform.from_sizes(
            sensor_size=(sensor_width, sensor_height),
            pixel_size=pixel_size,
            source_to_detector_distance=self.source_to_detector_distance,
        )

    @property
    def device_from_camera3d(self) -> geo.FrameTransform:
        """Get the FrameTransform for the device's camera3d_from_device frame (in the current pose).

        Args:
            camera3d_transform (FrameTransform): the "camera3d_from_device" frame transformation for the device.

        Returns:
            FrameTransform: the "device_from_camera3d" frame transformation for the device.
        """
        return geo.frame_transform(None)

    @property
    @abstractmethod
    def principle_ray(self) -> geo.Vector3D:
        """Get the principle ray for the device in the current pose in the device frame.

        The principle ray is the direction of the ray that passes through the center of the
        image. It points from the source toward the detector.

        Returns:
            Vector3D: the principle ray for the device as a unit vector.

        """
        return geo.v(0, 0, 1)
