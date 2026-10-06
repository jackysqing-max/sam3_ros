# SPDX-License-Identifier: Apache-2.0
"""Install the standalone sam3_ros ament Python package."""

from glob import glob

from setuptools import find_packages, setup

package_name = "sam3_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml", "LICENSE", "NOTICE", "README.md"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="siqin",
    maintainer_email="jackysqing@gmail.com",
    description="Reusable text-prompt SAM3 vision module for ROS 2",
    license="Apache-2.0",
    url="https://github.com/jackysqing-max/sam3_ros",
    extras_require={"test": ["pytest"]},
    entry_points={"console_scripts": [
        "sam3_mask_node = sam3_ros.sam3_mask_node:main",
        "sam3_image_file_node = sam3_ros.image_file_node:main",
    ]},
)
