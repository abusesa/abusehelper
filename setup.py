import os
import imp
from setuphelpers import setup, install_other

def generate_version():
    base_path, _ = os.path.split(__file__)
    module_path = os.path.join(base_path, "abusehelper", "core")

    module_info = imp.find_module("version", [module_path])
    version_module = imp.load_module("version", *module_info)

    version_module.generate(base_path)
    return version_module.version_str()
version = generate_version()

def is_package(path):
    try:
        imp.find_module(".", [path])
    except ImportError:
        return False
    return True

def collect_package(package, path=None):
    if path is None:
        path = os.path.join(*package.split("."))
    return _collect_package(package, path)

def _collect_package(package, path):
    if not is_package(path):
        return

    yield package, path

    for name in os.listdir(path):
        sub = os.path.join(path, name)
        for result in collect_package(package + "." + name, sub):
            yield result

def collect_package_data(src, dst):
    paths = list()

    cwd = os.getcwd()
    try:
        os.chdir(src)

        for dirpath, dirnames, filenames in os.walk(dst):
            for filename in filenames:
                normalized = os.path.normpath(os.path.join(dirpath, filename))
                paths.append(os.path.normpath(normalized))
    finally:
        os.chdir(cwd)

    return paths

install_other("idiokit")

packages = dict()
packages.update(collect_package("abusehelper"))
packages.update(collect_package("abusehelper.contrib"))

setup(
    name="abusehelper",
    version="2." + version,
    packages=packages,
    package_dir=packages,
    package_data={
        "abusehelper.contrib.confgen":
            collect_package_data("abusehelper/contrib/confgen", "config-template")
    },
    scripts=[
        "scripts/botnet",
        "scripts/roomreader"
    ],
    description="A framework for receiving and redistributing abuse feeds",
    long_description=(
        "AbuseHelper is a modular, scalable and robust " +
        "framework to help you in your abuse handling."
    ),
    author="Clarified Networks",
    author_email="contact@clarifiednetworks.com",
    url="https://bitbucket.org/clarifiednetworks/abusehelper",
    download_url="https://bitbucket.org/clarifiednetworks/abusehelper/downloads",
    license="MIT"
)
