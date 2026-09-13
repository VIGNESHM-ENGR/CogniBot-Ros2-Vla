from glob import glob

from setuptools import find_packages, setup

package_name = "cognibot_motion"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/config/so101", glob("config/so101/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Vignesh",
    maintainer_email="vigneshm1engr@gmail.com",
    description="Mode manager, safety filter, reachability query and fetch/place server.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "move_to_point = cognibot_motion.move_to_point:main",
            "pick_place_server = cognibot_motion.pick_place_server:main",
        ],
    },
)
