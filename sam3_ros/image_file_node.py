# SPDX-License-Identifier: Apache-2.0
"""Publish a local RGB image for camera-free SAM3 demos."""

import rclpy
from PIL import Image as PILImage
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


class ImageFileNode(Node):
    """Republish a still image with a fresh ROS timestamp."""

    def __init__(self):
        super().__init__("sam3_image_file_node")
        self.declare_parameter("image_path", "")
        self.declare_parameter("image_topic", "/image_raw")
        self.declare_parameter("frame_id", "camera_optical_frame")
        self.declare_parameter("publish_hz", 1.0)
        path = self.get_parameter("image_path").value
        rate = self.get_parameter("publish_hz").value
        if not path or rate <= 0:
            raise ValueError("Set image_path to an image file and publish_hz > 0")
        with PILImage.open(path) as image:
            rgb = image.convert("RGB")
            self.width, self.height = rgb.size
            self.data = rgb.tobytes()
        self.publisher = self.create_publisher(
            Image, self.get_parameter("image_topic").value, qos_profile_sensor_data,
        )
        self.timer = self.create_timer(1.0 / rate, self.publish_image)

    def publish_image(self):
        """Publish the loaded image with a timestamp for downstream matching."""
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.get_parameter("frame_id").value
        msg.height, msg.width = self.height, self.width
        msg.encoding, msg.step = "rgb8", self.width * 3
        msg.data = self.data
        self.publisher.publish(msg)


def main(args=None):
    """Run the image publisher."""
    rclpy.init(args=args)
    node = None
    try:
        node = ImageFileNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
