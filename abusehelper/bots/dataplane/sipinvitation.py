"""
Dataplane bot (SIP invite)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneSipinvitationBot(DataplaneBot):
    url = "https://dataplane.org/sipinvitation.txt"


if __name__ == "__main__":
    DataplaneSipinvitationBot.from_command_line().execute()
