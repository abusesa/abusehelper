from distutils.core import setup
import sys

setup(name="abusehelper",
      version="r211", #update this when creating packages
      packages=["abusehelper", 
                "abusehelper.core", 
                "abusehelper.thirdparty",
                "abusehelper.year3000",
                "idiokit"],
      description="A framework for receiving and redistributing Abuse Feeds",
      long_description="AbuseHelper is a modular, scalable and robust " + \
          "framework to help you in your abuse handling.",
      author="Clarified Networks",
      author_email="contact@clarifiednetworks.com",
      url="http://code.google.com/p/abusehelper",
      download_url="http://code.google.com/p/abusehelper/downloads/list",      
      scripts=["scripts/abusehelperctl"],
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
      data_files=[
                   ("/etc/abusehelper", 
                    ["example/customers.ini",
                     "example/config.ini"]
                   ),
                   ("/etc/abusehelper/templates", 
                    ["example/templates/dshield",
                     "example/templates/ircfeed"]
                    ),
                   ("/var/log/abusehelper",
                    [])

                 ]

      )





