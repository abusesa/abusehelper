from setuptools import setup, find_packages

import abusehelper

setup(
    name="abusehelper",
    version=abusehelper.__version__,
    description="A framework for receiving and redistributing abuse feeds",
    long_description=(
        "AbuseHelper is a modular, scalable and robust " +
        "framework to help you in your abuse handling."
    ),
    author="Clarified Networks",
    author_email="contact@clarifiednetworks.com",
    url="https://github.com/abusesa/abusehelper/",
    license="MIT",
    packages=find_packages(exclude=["*.tests"]),
    entry_points={
        "console_scripts": [
            "botnet=abusehelper.tools.botnet:main",
            "roomreader=abusehelper.tools.roomreader:main"
        ]
    },
    install_requires=[
        "idiokit>=2.8.0,<3.0.0"
    ]
)
