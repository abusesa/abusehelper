"""
Dataplane bot (DNS recursion desired)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneDnsrdBot(DataplaneBot):
    url = "https://dataplane.org/dnsrd.txt"


if __name__ == "__main__":
    DataplaneDnsrdBot.from_command_line().execute()
