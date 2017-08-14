"""
Dataplane bot (VNC RFB)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneVncrfbBot(DataplaneBot):
    url = "https://dataplane.org/vncrfb.txt"


if __name__ == "__main__":
    DataplaneVncrfbBot.from_command_line().execute()
