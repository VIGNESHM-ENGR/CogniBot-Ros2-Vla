from glob import glob

from setuptools import find_packages, setup

package_name = "cognibot_common"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Vignesh",
    maintainer_email="vigneshm1engr@gmail.com",
    description="Shared utilities: robot registry, QoS presets, image helpers, GPU monitor.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gpu_monitor = cognibot_common.gpu_monitor:main",
        ],
    },
)
