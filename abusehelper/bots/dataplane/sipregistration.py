"""
Dataplane bot (SIP register)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneSipregistrationBot(DataplaneBot):
    url = "https://dataplane.org/sipregistration.txt"


if __name__ == "__main__":
    DataplaneSipregistrationBot.from_command_line().execute()
