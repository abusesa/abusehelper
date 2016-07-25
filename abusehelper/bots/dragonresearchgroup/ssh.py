"""
Dragon research group bot (SSH)

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

from . import DragonBot


class DragonSshBot(DragonBot):
    url = "https://dragonresearchgroup.org/insight/sshpwauth.txt"


if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
