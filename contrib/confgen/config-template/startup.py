import os
from abusehelper.core.config import *
from abusehelper.core.startup import *

def locate(*path):
    base_dir, _ = os.path.split(__file__)
    return os.path.abspath(os.path.join(base_dir, *path))

class Bot(Startup):
    bot_name = dynamic("%(name)s")

    # Unomment the following lines, and the bots will keep
    # persistent state and log to files, respectively.
    #bot_state_file = dynamic(locate("state", "%(name)s.state"))
    #log_file = dynamic(locate("log", "%(name)s.log"))

    # The default credentials used for XMPP connections.
    xmpp_jid = "@XMPP_JID@"
    xmpp_password = "@XMPP_PASSWORD@"

    # The XMPP multi-user chat room used for bot control.
    service_room = "@SERVICE_ROOM@"

# Class for launching abusehelper core bots.
class CoreBot(Bot):
    module = dynamic("abusehelper.core.%(name)s")

# Class for launching our custom bots.
class CustomBot(Bot):
    module = dynamic(locate("custom", "%(name)s.py"))

# Define function "configs" to bypass the default startup behavior of
# harvesting this module's namespace for config objects.
def configs():
    # Load the configs from this module's global namespace.
    for value in default_configs(globals()):
        yield value

    # Go through the custom bot directory, and launch all modules
    # named *.sanitizer.py automatically.
    for filename in os.listdir(locate("custom")):
        if filename.endswith(".sanitizer.py"):
            yield CustomBot(name=filename[:-3])

# Manual startup definitions start here

mailer = CoreBot(smtp_host="@SMTP_HOST@",
                 smtp_port="@SMTP_PORT@",
                 smtp_auth_user="@SMTP_AUTH_USER@",
                 smtp_auth_password="@SMTP_AUTH_PASSWORD@",
                 mail_sender="@MAIL_SENDER@")
wikibot = CoreBot()
dshield = CoreBot()
roomgraph = CoreBot()
historian = CoreBot()
runtime = CoreBot(config=locate("runtime.py"))
