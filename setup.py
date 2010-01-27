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
      version="1.r"+version,
      packages=["abusehelper", 
                "abusehelper.core", 
                "abusehelper.thirdparty",
                "abusehelper.year3000",
                "idiokit"],
      data_files = [('share/examples/abusehelper', 
	["example/config.ini",
	 "example/customers.ini"],
       ),
       ('share/examples/abusehelper/templates',
	 ["example/templates/dshield",
	 "example/templates/ircfeed"],
       )],
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


if sys.argv[1] == 'install':

    ahgroup="abusehel"
    ahuser="abusehel"
    groupadd=""
    useradd="useradd %s" % (ahuser)

    if os.uname()[0] == 'OpenBSD':
	ahgroup="_abusehe"
	ahuser="_abusehe"
        groupadd="groupadd %s" % (ahgroup) 
        useradd="useradd -m -g %s %s" % (ahgroup, ahuser)

 
    if not os.path.exists("/etc/abusehelper/"):
        #todo, rather check if the user actually exists.
        print 'To create abusehelper user and groups:\n' + \
            ' sudo %s\n' % (groupadd) + \
            ' sudo %s\n' % (useradd)

        print 'To create abusehelper config directory:\n' + \
            ' sudo mkdir /etc/abusehelper\n' + \
            ' sudo chown root:%s /etc/abusehelper\n' % (ahgroup) + \
            ' sudo chmod 750 /etc/abusehelper' 

        print '\nTo configure:\n' + \
            ' sudo cp -r example/* /etc/abusehelper/\n' + \
            'And then edit config.ini and customers.ini in /etc/abusehelper/'

    if not os.path.exists("/var/log/abusehelper/"):
        print '\nTo create log directory:\n' +  \
            ' sudo mkdir /var/log/abusehelper\n' + \
            ' sudo chown %s:%s /var/log/abusehelper\n' % (ahuser, ahgroup) + \
            ' sudo chmod 770 /var/log/abusehelper' 
        
        
        
    



