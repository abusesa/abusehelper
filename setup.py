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
        "abusehelper.contrib.reprbot",
        "abusehelper.contrib.opencollabbot",
        "abusehelper.contrib.wikiruntime",
        "abusehelper.contrib.arbor",
        "abusehelper.contrib.dragon",
        "abusehelper.contrib.abusechbot",
        "abusehelper.contrib.honeypotbot",
        "abusehelper.contrib.cleanmxbot",
        "abusehelper.contrib.phishtankbot",
        "abusehelper.contrib.runtime2dot",
        "abusehelper.contrib.mdlbot",
        "abusehelper.contrib.urllistmailbot",
        "abusehelper.contrib.experts"],
      package_dir={
        "abusehelper.contrib": "contrib",	
        "abusehelper.contrib.confgen": "contrib/confgen",
        "abusehelper.contrib.archivebot": "contrib/archivebot",
        "abusehelper.contrib.bridgebot": "contrib/bridgebot",
        "abusehelper.contrib.tailbot": "contrib/tailbot",
        "abusehelper.contrib.windowbot": "contrib/windowbot",
        "abusehelper.contrib.reprbot": "contrib/reprbot",
        "abusehelper.contrib.opencollabbot": "contrib/opencollabbot",
        "abusehelper.contrib.wikiruntime": "contrib/wikiruntime",
        "abusehelper.contrib.arbor": "contrib/arbor",
        "abusehelper.contrib.dragon": "contrib/dragon",
        "abusehelper.contrib.abusechbot": "contrib/abusechbot",
        "abusehelper.contrib.honeypotbot": "contrib/honeypotbot",
        "abusehelper.contrib.cleanmxbot": "contrib/cleanmxbot",
        "abusehelper.contrib.phishtankbot": "contrib/phishtankbot",
        "abusehelper.contrib.runtime2dot": "contrib/runtime2dot",
        "abusehelper.contrib.urllistmailbot": "contrib/urllistmailbot/",
        "abusehelper.contrib.mdlbot": "contrib/mdlbot/",
        "abusehelper.contrib.experts": "contrib/experts",
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
