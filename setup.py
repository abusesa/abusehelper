import os
import imp
import sys
import errno
from distutils.core import setup
from distutils.dir_util import remove_tree
from distutils.util import convert_path
from distutils.command.build import build as _build
from distutils.command.install import install as _install


class Build(_build):
    def run(self):
        clean = self.distribution.reinitialize_command("clean", reinit_subcommands=True)
        clean.all = True
        self.distribution.run_command("clean")
        _build.run(self)


class Install(_install):
    def run(self):
        build_py = self.distribution.get_command_obj("build_py")
        if self.distribution.packages:
            for package in self.distribution.packages:
                package_dir = build_py.get_package_dir(package)
                rmtree(os.path.join(self.install_lib, package_dir))
        install_other("idiokit")
        _install.run(self)


def rmtree(path):
    try:
        remove_tree(convert_path(path))
    except OSError, err:
        if err.errno != errno.ENOENT:
            raise


def install_other(subdir):
    cwd = os.getcwd()
    path = os.path.join(cwd, subdir)

    try:
        os.chdir(path)
    except OSError, error:
        if error.errno not in (errno.ENOENT, errno.ENOTDIR):
            raise
        print >> sys.stderr, "Could not find directory %r" % path
        return

    try:
        module_info = imp.find_module("setup", ["."])
        imp.load_module("setup", *module_info)
    finally:
        os.chdir(cwd)


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


packages = dict()
packages.update(collect_package("abusehelper"))
packages.update(collect_package("abusehelper.bots"))

setup(
    name="abusehelper",
    version="2.1.0",
    description="A framework for receiving and redistributing abuse feeds",
    long_description=(
        "AbuseHelper is a modular, scalable and robust " +
        "framework to help you in your abuse handling."
    ),
    author="Clarified Networks",
    author_email="contact@clarifiednetworks.com",
    url="https://github.com/abusesa/abusehelper/",
    license="MIT",
    packages=packages,
    package_dir=packages,
    scripts=[
        "scripts/botnet",
        "scripts/roomreader"
    ],
    install_requires=[
        "idiokit>=2.2.0,<3.0.0"
    ],
    cmdclass={
        "build": Build,
        "install": Install
    }
)
