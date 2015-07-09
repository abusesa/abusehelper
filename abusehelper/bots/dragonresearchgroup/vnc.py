"""
Dragon research group bot (VNC)

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

from . import DragonBot


class DragonVncBot(DragonBot):
    url = "https://dragonresearchgroup.org/insight/vncprobe.txt"


if __name__ == "__main__":
    DragonVncBot.from_command_line().execute()
