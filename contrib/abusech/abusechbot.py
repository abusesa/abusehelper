# -*- coding: utf-8 -*-
"""
    AbuseCH feed handler
"""
__authors__ = "Toni Huttunen, Sebastian Turpeinen and Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot

class AbuseCHBot(RSSBot):
    feeds = bot.ListParam(default=[
        "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
        "https://zeustracker.abuse.ch/rss.php",
        "http://amada.abuse.ch/palevotracker.php?rssfeed",
        "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=configurls",
        "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=binaryurls",
        "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=dropurls"])

    def create_event(self, **kw):
        if kw.get("description", None) == None:
            return None
        description = kw["description"]

        event = events.Event()

        title = kw.get("title", None)
        if title:
            parts = title.split("(")
            if len(parts) > 1:
                event.add("time", parts[1].rstrip(")"))

        for part in description.split(","):
            pair = part.split(":")
            if len(pair) < 2:
                continue
            key = pair[0].strip()
            value = pair[1].strip()

            levels = {'1': 'Bulletproof hosted',
                      '2': 'Hacked webserver',
                      '3': 'Free hosting service',
                      '4': 'Unknown',
                      '5': 'Hosted on a FastFlux botnet'}

            if not value:
                continue
            elif key == "AS":
                if value.startswith("AS"):
                    value = value[2:]
                event.add("asn", value)
            elif key == "Status":
                event.add("status", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key in ["Country", "Host", "Status"]:
                event.add(key.lower(), value)
            elif key == "SBL":
                event.add("sbl", 
                          "http://www.spamhaus.org/sbl/sbl.lasso?query=%s" % 
                          (value))
            elif key == "Level":
                if value in levels:
                    event.add("level", levels[value])
                else:
                    event.add("level", value)
            url = kw.get('url', '')

            if "zeus" in url:
                event.add("malware", "zeus")
            elif "spyeye" in url:
                event.add("malware", "spyeye")
            elif "palevo" in url:
                event.add("malware", "palevo")

        if not event.contains("ip"):
            return None

        if kw.get('source', ''):
            event.add('source', kw['source'])

        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()
