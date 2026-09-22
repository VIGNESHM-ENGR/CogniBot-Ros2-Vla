from glob import glob

from setuptools import find_packages, setup

package_name = "cognibot_laya"

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
    description="RLCD decision layer: typed decisions over the symbolic scene state (ADR-0008).",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": ["laya_decision = cognibot_laya.decision_node:main"],
    },
)
