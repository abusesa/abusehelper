from abusehelper.core import imapbot

class ShadowSpambotBot(imapbot.IMAPService):
    def __init__(self, **keys):
        imapbot.IMAPService.__init__(self, **keys)

if __name__ == "__main__":
    ShadowSpambotBot.from_command_line().execute()
