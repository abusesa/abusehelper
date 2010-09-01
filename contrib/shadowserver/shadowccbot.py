from abusehelper.core import imapbot

class ShadowCCBot(imapbot.IMAPService):
    def __init__(self, **keys):
        imapbot.IMAPService.__init__(self, **keys)

if __name__ == "__main__":
    ShadowCCBot.from_command_line().execute()
