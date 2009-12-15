from distutils.core import setup

setup(name="abusehelper",
      packages=["abusehelper", 
                "abusehelper.core", 
                "abusehelper.thirdparty",
                "abusehelper.year3000",
                "idiokit"],
      scripts=["scripts/abusehelperctl"]
      )
