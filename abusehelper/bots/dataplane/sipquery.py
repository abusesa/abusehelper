"""
Dataplane bot (SIP query)

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

from . import DataplaneBot


class DataplaneSipqueryBot(DataplaneBot):
    url = "https://dataplane.org/sipquery.txt"


if __name__ == "__main__":
    DataplaneSipqueryBot.from_command_line().execute()
