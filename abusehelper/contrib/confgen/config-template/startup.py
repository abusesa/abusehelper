import os

from abusehelper.core.startup import Bot

xmpp_jid = "@XMPP_JID@"
xmpp_password = "@XMPP_PASSWORD@"
service_room = "@SERVICE_ROOM@"
enable_mailer = "@ENABLE_MAILER@"

def basic(name, *args, **attrs):
    template = Bot.template(
        xmpp_jid=xmpp_jid,
        xmpp_password=xmpp_password,
        service_room=service_room,

        ## Uncomment the following lines, and the bots will keep
        ## persistent state and log to files, respectively.
        # bot_state_file=os.path.join("state", name + ".state"),
        # log_file=os.path.join("log", name + ".log")
    )
    return template(name, *args, **attrs)

def configs():
    # Launch a fine selection of abusehelper.core.* bots

    yield basic("runtime", config="./runtime.py")
    yield basic("roomgraph")
    yield basic("archivebot", archive_dir="./archive")
    yield basic("dshield")

    # Maybe run the mailer too

    if enable_mailer:
        yield basic("mailer",
            smtp_host="@SMTP_HOST@",
            smtp_port="@SMTP_PORT@",
            smtp_auth_user="@SMTP_AUTH_USER@",
            smtp_auth_password="@SMTP_AUTH_PASSWORD@",
            mail_sender="@MAIL_SENDER@")

    # Launch a nice source bot from the contrib. Remember to explicitly
    # define the bot module name, as this is not a core bot!

    yield basic("malwaredomainlist", "abusehelper.contrib.malwaredomainlist.updates")

    # Find and launch modules named custom/*.sanitizer.py

    for filename in os.listdir("./custom"):
        if filename.endswith(".sanitizer.py"):
            yield basic(filename[:-3], os.path.join("custom", filename))
