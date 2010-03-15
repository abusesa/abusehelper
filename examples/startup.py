import os
from abusehelper.core.config import *

class Bot(Config):
    def __init__(self, name, **attrs):
        self.attrs = dict(
            # Overwrite these only when you really know what you are doing.
            bot_name=name,
            module="abusehelper.core."+name,
            
            # Uncomment the following line, and the bots will keep
            # persistent state.
            #bot_state_file="/var/log/abusehelper/"+name,

            # Uncomment the following line, and instead of printing to the
            # console the bots will log to files.
            #log_file="/var/log/abusehelper/"+name,

            # Bots that provide services gather in lobby.  This room
            # is used for communicating configuration to different
            # bots.
            service_room="my-usecase",
            
            # The default credentials which for logging in to the XMPP
            # service.
            xmpp_jid="abusebots@ah.example.com",
            xmpp_password="yourpassword",
            )
        self.attrs.update(attrs)

    def startup(self):
        return self.attrs

def configs():
    base_dir = os.path.dirname(__file__)

    return [
        Bot("runtime", 
            config=os.path.join(base_dir, "runtime.py")),
        
        Bot("mailer",
            # Mailer will use this server and port for sending mails.
            # You can use e.g. the traditional 25 or the authenticated 
            # submission port 587.
            smtp_host = "smtp.example.com",
            smtp_port = 25,
            
            # From whom it looks like the mail reports came from.
            mail_sender = "abusereports@example.com",
            
            # If you use authenticated submission port, put here
            # your username (without the domain) and password.
            #smtp_auth_user = "username",
            #smtp_auth_password = "password",
            ),
        
        Bot("dshield",
            # Override the default 1h polling interval. 
            # The interval is given in seconds,
            # e.g. poll_interval = 600 means polling every 10 minutes.
            #poll_interval = 600,
            
            # Use Cymru WHOIS service for determining ASNs.
            #use_cymru_whois = True,
            ),            
        
        # These are just for starting the roomgraph and historian services.
        # No extra startup options needed.
        Bot("roomgraph"),
        Bot("historian"),

        # Bot("atlassrf",
        #     feed_url=https://atlas.arbor.net/srf/feeds/889214124/?alt=csv,
        #     # Override the default 1h polling interval.  The
        #     # interval is given in seconds, e.g. poll_interval=600
        #     # means polling every 10 minutes.
        #     #poll_interval = 600
        #     )
        ]
