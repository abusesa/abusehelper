"""
Dataplane bot (SSH client)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneSshclientBot(DataplaneBot):
    url = "https://dataplane.org/sshclient.txt"


if __name__ == "__main__":
    DataplaneSshclientBot.from_command_line().execute()
