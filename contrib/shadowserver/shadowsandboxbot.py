from abusehelper.core import imapbot

class ShadowSandboxBot(imapbot.IMAPService):
    def __init__(self, **keys):
        imapbot.IMAPService.__init__(self, **keys)

if __name__ == "__main__":
    ShadowSandboxBot.from_command_line().execute()
