"""
Dataplane bot (DNS CH TXT version.bind)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneDnsversionBot(DataplaneBot):
    url = "https://dataplane.org/dnsversion.txt"


if __name__ == "__main__":
    DataplaneDnsversionBot.from_command_line().execute()
