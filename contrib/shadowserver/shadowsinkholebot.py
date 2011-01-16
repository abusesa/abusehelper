from abusehelper.core import shadowservermail

class ShadowSinkholeBot(shadowservermail.ShadowServerMail):
    pass

if __name__ == "__main__":
    ShadowSinkholeBot.from_command_line().execute()
