import os
import imp
import sys
import errno
from distutils.core import setup as _setup
from distutils.dir_util import remove_tree
from distutils.util import convert_path
from distutils.command.install import install as _install
from distutils.command.build import build as _build

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

def setup(*args, **keys):
    keys = dict(keys)
    cmdclass = dict(keys.pop("cmdclass", dict()))

    install_base = cmdclass.get("install", _install)
    class install(install_base):
        def run(self):
            self.distribution.run_command("clean")

            build_py = self.distribution.get_command_obj("build_py")
            if self.distribution.packages:
                for package in self.distribution.packages:
                    package_dir = build_py.get_package_dir(package)
                    rmtree(os.path.join(self.install_lib, package_dir))
            install_base.run(self)
    cmdclass["install"] = install

    options = keys.pop("options", dict())
    clean = options.setdefault("clean", dict())
    clean.setdefault("all", True)

    return _setup(cmdclass=cmdclass,
                  options=options,
                  *args, **keys)
