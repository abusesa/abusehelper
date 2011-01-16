from abusehelper.core import shadowservermail

class ShadowSpambotBot(shadowservermail.ShadowServerMail):
    pass

if __name__ == "__main__":
    ShadowSpambotBot.from_command_line().execute()
