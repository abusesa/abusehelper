import os
import sys
import imp
import warnings
import platform
from distutils.core import setup

if sys.version_info < (2, 5):
    print >> sys.stderr, "Error: AbuseHelper requires Python 2.5 or higher",
    print >> sys.stderr, "(you are running Python %s)." % platform.python_version()
    sys.exit(1)

def generate_version():
    base_path, _ = os.path.split(__file__)
    module_path = os.path.join(base_path, "abusehelper", "core")

    module_info = imp.find_module("version", [module_path])
    version_module = imp.load_module("version", *module_info)
    
    version_module.generate(base_path)
    return version_module.version()


version = generate_version()
if version is None:
    print >> sys.stderr, "No version info available. Quitting."
    sys.exit(1)
if not version.isdigit():
    warnings.warn("This is not a clean checkout (version %r)." % version)

setup(name="abusehelper",
      version="2.r"+version,
      packages=[
        "abusehelper", 
        "abusehelper.core", 
        "idiokit", 
        "abusehelper.contrib",
        "abusehelper.contrib.confgen"],
      package_dir={
        'abusehelper.contrib.confgen': 'contrib/confgen',
        'abusehelper.contrib': 'contrib',	
	},
      package_data={
        'abusehelper.contrib.confgen': 
        [
	  'config-template/*.py',
          'config-template/custom/*.py',
          'config-template/template/default'
          ]
       },
      description="A framework for receiving and redistributing Abuse Feeds",
      long_description="AbuseHelper is a modular, scalable and robust " + \
          "framework to help you in your abuse handling.",
      author="Clarified Networks",
      author_email="contact@clarifiednetworks.com",
      url="http://code.google.com/p/abusehelper",
      download_url="http://code.google.com/p/abusehelper/downloads/list",      
      scripts=["scripts/abusehelperctl","scripts/roomreader"],
      license="MIT",
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Other Environment",
          "Topic :: Internet",
          "Topic :: Security",
          "Intended Audience :: Information Technology",
          "Intended Audience :: Telecommunications Industry",
          "License :: Freely Distributable",
          "Programming Language :: Python"],
      )

