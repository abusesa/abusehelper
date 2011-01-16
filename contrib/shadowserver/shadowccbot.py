from abusehelper.core import shadowservermail

class ShadowCCBot(shadowservermail.ShadowServerMail):
    pass

if __name__ == "__main__":
    ShadowCCBot.from_command_line().execute()
