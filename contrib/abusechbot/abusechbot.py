# -*- coding: utf-8 -*-
"""
    AbuseCH feed handler
"""
__authors__ = "Toni Huttunen, Joachim Viide and Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import urllib2
import xml.etree.cElementTree as etree
import idiokit
from abusehelper.core import bot, events, utils
from abusehelper.contrib.rssbot.rssbot import RSSBot

class AbuseCHBot(RSSBot):
    feeds = bot.ListParam(default=[
            "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
            "https://zeustracker.abuse.ch/rss.php",
            "http://amada.abuse.ch/palevotracker.php?rssfeed"])

    def create_event(self, **kw):
        if kw.get("description", None) == None:
            return None
        description = kw["description"]

        event = events.Event()

        for part in description.split(","):
            pair = part.split(":")
            if len(pair) < 2:
                continue
            key = pair[0].strip()
            value = pair[1].strip()

            if not value:
                continue
            elif key == "AS":
                if value.startswith("AS"):
                    value = value[2:]
                event.add("asn", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key == "Country":
                event.add("country", value)
            elif key == "Host":
                event.add("host", value)
            elif key == "Status":
                event.add("status", value)
            url = kw.get('url', '')
            if "zeus" in url:
                event.add("malware", "zeus")
            elif "spyeye" in url:
                event.add("malware", "spyeye")
            elif "palevo" in url:
                event.add("malware", "palevo")

        if not event.contains("asn") or not event.contains("ip"):
            return None

        if kw.get('source', ''):
            event.add('source', kw[source])

        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()

