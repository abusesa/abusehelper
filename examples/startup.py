import os
from abusehelper.core.config import *
from abusehelper.core.startup import *

class CoreBot(Startup):
    # Overwrite these only when you really know what you are doing.
    module = dynamic("abusehelper.core.%(name)s")
    bot_name = dynamic("%(name)s")

    # Comment out this part, and the bots won't keep persistent state.
    bot_state_file = dynamic("/var/log/abusehelper/%(name)s")

    # Bots that provide services gather in lobby.
    # This room is used for communicating configuration to different bots.
    service_room = "my-usecase"

    # The default credentials which for logging in to the XMPP service.
    # You can register new bots for example by running the following command:
    #   ejabberdctl register abusebots ah.cert.ee yourpassword 
    xmpp_jid = "abusebots@ah.example.com"
    xmpp_password = "yourpassword"

    # Uncomment the following line, and instead of printing to the
    # console the bots will log to files. The magical %(name)s variable
    # gets converted to the bot name, so bot launched created like
    #  example = CoreBot(...)
    # will use the file /var/log/abusehelper/example.log for logging.
    log_file = dynamic("/var/log/abusehelper/%(name)s.log")

base_dir, _ = os.path.split(__file__)
runtime = CoreBot(config=os.path.join(base_dir, "runtime.py")) 

mailer = CoreBot(# Mailer will use this server and port for sending mails.
                 # You can use e.g. the traditional 25 or the authenticated 
                 # submission port 587.
                 smtp_host = "smtp.example.com",
                 smtp_port = 25,

                 # From whom it looks like the mail reports came from.
                 mail_sender = "abusereports@example.com",

                 # If you use authenticated submission port, put here your username 
                 # (without the domain) and password.
                 #smtp_auth_user = "username",
                 #smtp_auth_password = "password",
                 )

dshield = CoreBot(# Override the default 1h polling interval. The interval is given in seconds,
                  # e.g. poll_interval = 600 means polling every 10 minutes.
                  #poll_interval = 600,

                  # Use Cymru WHOIS service for determining ASNs.
                  #use_cymru_whois = True,
                  )

# These are just for starting the roomgraph and historian services.
# No extra startup options needed.
roomgraph = CoreBot()
historian = CoreBot()

# atlassrf = CoreBot(feed_url = https://atlas.arbor.net/srf/feeds/889214124/?alt=csv
#                    # Override the default 1h polling interval. The interval is given in seconds,
#                    # e.g. poll_interval = 600 means polling every 10 minutes.
#                    #poll_interval = 600
#                    )
