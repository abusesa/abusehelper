from . import DragonBot


class DragonSshBot(DragonBot):
    url = "http://dragonresearchgroup.org/insight/sshpwauth.txt"


if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
