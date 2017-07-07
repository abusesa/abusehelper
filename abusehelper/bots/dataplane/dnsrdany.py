"""
Dataplane bot (DNS recursion desired IN ANY)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneDnsrdanyBot(DataplaneBot):
    url = "https://dataplane.org/dnsrdany.txt"


if __name__ == "__main__":
    DataplaneDnsrdanyBot.from_command_line().execute()
