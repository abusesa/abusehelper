from abusehelper.core import bot, events
from abusehelper.contrib.tailbot.tailbot import TailBot

import time

def convert_date(value):
    try:
        ts = time.strptime(value, "%d/%b/%Y:%H:%M:%S +0000")
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", ts)
    except ValueError:
        ts = value

    return ts


class AccessLogBot(TailBot):
    path = bot.Param("access_log file path")

    def parse(self, line, _):
        line = line.strip()
        if not line:
            return

        # LogFormat "%h %l %u %t \"%r\" %>s %b" common
        # LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"" combined

        facts = {}

        try:
            left, _, right = line.partition(" ")
            facts["ip"] = left.strip()
            right = right.strip()

            left, _, right = right.partition(" ")
            if left != "-":
                facts["ident"] = left.strip()
                right = right.strip()

            left, _, right = right.partition(" ")
            if left != "-":
                facts["user"] = left.strip()
                right = right.strip()

            if right.startswith("["):
                left, _, right = right[1:].partition("]")
                facts["timestamp"] = convert_date(left.strip())
                right = right.strip()
            else:
                raise InputError("could not parse timestamp")

            if right.startswith("\""):
                left, _, right = right[1:].partition("\"")
                facts["request"] = left.strip()
                right = right.strip()
            else:
                raise InputError("could not parse request")

            left, _, right = right.partition(" ")
            if left != "-":
                facts["status"] = left.strip()
                right = right.strip()

            left, _, right = right.partition(" ")
            if left != "-":
                facts["bytes"] = left.strip()
                right = right.strip()

            if right.startswith("\""):
                left, _, right = right[1:].partition("\"")
                if left != "-":
                    facts["referer"] = left
                right = right.strip()
            else:
                raise InputError("could not parse referer")

            if right.startswith("\""):
                left, _, right = right[1:].partition("\"")
                if left != "-":
                    facts["user_agent"] = left
            else:
                raise InputError("could not parse user_agent")

        except InputError:
            # All good
            pass


        if facts["request"]:
            # Split request also into three parts
            method, url, protocol = facts["request"].split(" ", 3)
            facts["method"]   = method
            facts["url"]      = url
            facts["protocol"] = protocol


        if facts["user_agent"]:
            # Split user agent into software-version key-value pairs
            uatemp = facts["user_agent"].strip()
            facts["product"] = list()
            comments = list()
            while uatemp:
                if uatemp.startswith("("):
                    left, _, right = uatemp[1:].partition(")")
                    comments.append(left.strip())
                    uatemp = right.strip()
                else:
                    left, _, right = uatemp.strip().partition(" ")
                    try:
                        sw, version = left.split("/")
                        if sw and version:
                            facts[sw.lower()] = version
                            facts["product"].append(sw+"/"+version)
                    except ValueError:
                        continue
                    uatemp = right.strip()

        return events.Event(facts)


if __name__ == "__main__":
    AccessLogBot.from_command_line().execute()
