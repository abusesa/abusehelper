from abusehelper.core import imapbot

class ShadowSinkholeBot(imapbot.IMAPService):
    def __init__(self, **keys):
        imapbot.IMAPService.__init__(self, **keys)

if __name__ == "__main__":
    ShadowSinkholeBot.from_command_line().execute()
