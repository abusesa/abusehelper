import os
import sys
import imp
import errno
import platform
from distutils.core import setup

if sys.version_info < (2, 5):
    print >> sys.stderr, "Error: AbuseHelper requires Python 2.5 or higher",
    print >> sys.stderr, "(you are running %s)." % platform.python_version()
    sys.exit(1)

def generate_version():
    base_path, _ = os.path.split(__file__)
    module_path = os.path.join(base_path, "abusehelper", "core")

    module_info = imp.find_module("version", [module_path])
    version_module = imp.load_module("version", *module_info)
    
    version_module.generate(base_path)
    return version_module.version_str()
version = generate_version()

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
install_other("idiokit")

setup(name="abusehelper",
      version="2." + version,
      packages=[
        "abusehelper", 
        "abusehelper.core", 
        "abusehelper.contrib",
        "abusehelper.contrib.confgen",
        "abusehelper.contrib.archivebot",
        "abusehelper.contrib.tailbot",
        "abusehelper.contrib.bridgebot",
        "abusehelper.contrib.windowbot",
        "abusehelper.contrib.reprbot"],
      package_dir={
        "abusehelper.contrib": "contrib",	
        "abusehelper.contrib.confgen": "contrib/confgen",
        "abusehelper.contrib.archivebot": "contrib/archivebot",
        "abusehelper.contrib.bridgebot": "contrib/bridgebot",
        "abusehelper.contrib.tailbot": "contrib/tailbot",
        "abusehelper.contrib.windowbot": "contrib/windowbot",
        "abusehelper.contrib.reprbot": "contrib/reprbot"
	},
      package_data={
        "abusehelper.contrib.confgen":
            [
            "confgen/*.py",
            "confgen/config-template/*.py",
            "confgen/config-template/custom/*.py",
            "confgen/config-template/template/default"
            ]
        },
      description="A framework for receiving and redistributing abuse feeds",
      long_description="AbuseHelper is a modular, scalable and robust " + \
          "framework to help you in your abuse handling.",
      author="Clarified Networks",
      author_email="contact@clarifiednetworks.com",
      url="https://bitbucket.org/clarifiednetworks/abusehelper",
      download_url="https://bitbucket.org/clarifiednetworks/abusehelper/downloads",
      scripts=[
        "scripts/abusehelperctl",
        "scripts/roomreader"
        ],
      license="MIT",
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Topic :: Internet",
        "Topic :: Security",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Telecommunications Industry",
        "License :: Freely Distributable",
        "Programming Language :: Python"
        ],
      )
