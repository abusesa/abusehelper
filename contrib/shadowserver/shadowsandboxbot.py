from abusehelper.core import shadowservermail

class ShadowSandboxBot(shadowservermail.ShadowServerMail):
    pass

if __name__ == "__main__":
    ShadowSandboxBot.from_command_line().execute()
