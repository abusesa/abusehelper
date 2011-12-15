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

setup(
    name="abusehelper",
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
        "abusehelper.contrib.danger",
        "abusehelper.contrib.spamhaus",
        "abusehelper.contrib.rssbot",
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
        "abusehelper.contrib.danger": "contrib/danger",
        "abusehelper.contrib.spamhaus": "contrib/spamhaus",
        "abusehelper.contrib.rssbot": "contrib/rssbot",
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
            collect_package_data("contrib/confgen", "config-template")
    },
    scripts=[
        "scripts/abusehelperctl",
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
