from distutils.core import setup
import sys,os

setup(name="abusehelper",
      version="1.r247-5", #update this when creating packages
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
    if not os.path.exists("/etc/abusehelper/"):

        print 'To create abusehelper config directory:\n' + \
            ' mkdir /etc/abusehelper\n' + \
            ' chown abusehel:abusehel /etc/abusehelper\n' + \
            ' chmod 750 /etc/abusehelper'

        print '\nTo configure:\n' + \
            ' cp -r example/* /etc/abusehelper/\n' + \
            'And then edit config.ini and customers.ini'

    if not os.path.exists("/var/log/abusehelper/"):
        print '\nTo create log directory:\n' +  \
            ' mkdir /var/log/abusehelper\n' + \
            ' chown abusehel:abusehel /var/log/abusehelper\n' + \
            ' chmod 770 /var/log/abusehelper' 
        
        
        
    



