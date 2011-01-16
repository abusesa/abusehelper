from abusehelper.core import shadowservermail

class ShadowDroneBot(shadowservermail.ShadowServerMail):
    pass

if __name__ == "__main__":
    ShadowDroneBot.from_command_line().execute()
