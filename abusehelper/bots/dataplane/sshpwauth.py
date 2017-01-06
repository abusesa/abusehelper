"""
Dataplane bot (SSH password authentication)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneSshpwauthBot(DataplaneBot):
    url = "https://dataplane.org/sshpwauth.txt"


if __name__ == "__main__":
    DataplaneSshpwauthBot.from_command_line().execute()
