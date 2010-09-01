from abusehelper.core import imapbot

class ShadowDroneBot(imapbot.IMAPService):
    def __init__(self, **keys):
        imapbot.IMAPService.__init__(self, **keys)

if __name__ == "__main__":
    ShadowDroneBot.from_command_line().execute()
