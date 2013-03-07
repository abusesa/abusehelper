"""
Project Honeypot feed handler.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import socket
from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot


class ProjectHoneyPotBot(RSSBot):
    feeds = bot.ListParam(default=[
            "http://www.projecthoneypot.org/list_of_ips.php?by=1&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=4&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=7&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=10&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=13&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=16&rss=1",
            "http://www.projecthoneypot.org/list_of_ips.php?by=19&rss=1"])

    def parse_ip(self, string):
        for addr_type in (socket.AF_INET, socket.AF_INET6):
            try:
                return socket.inet_ntop(addr_type, socket.inet_pton(addr_type, string))
            except (ValueError, socket.error):
                pass
        return None

    def create_event(self, source, **keys):
        event = events.Event()
        event.add("feed url", source)
        # handle title data
        descriptions = {'H': 'harvester',
                    'S': 'spam server',
                    'D': 'dictionary attacker',
                    'W': 'bad web host',
                    'C': 'comment spammer',
                    'R': 'rule breaker'}
        title = keys.get("title", None)
        if title is None:
            return None  # No title, no ip or types
        pieces = title.split(" | ", 1)
        if len(pieces) == 1:
            ip = pieces[0]
            types = ""
        else:
            ip, types = pieces
        if types == "Se":  # Not really an abuse event (e.g. google bots).
            return None
        if self.parse_ip(ip) is None:
            self.log.error("Malformed RSS title: %s", title)
            return None
        items = []
        for item in descriptions:
            if item in types:
                items.append(descriptions[item])
        if items:
            desc = "This host is most likely part of SPAM infrastructure as: " + \
                ", ".join(items) + "."
        else:
            desc = "This host is most likely part of SPAM infrastructure."
        event.add('description', desc)
        url = "http://www.projecthoneypot.org/ip_" + ip
        event.add("description url", url)
        event.add("ip", ip)

        # handle description data
        description = keys.get("description", None)
        if description:
            for part in description.split(" | "):
                pair = part.split(":", 1)
                if len(pair) < 2:
                    continue

                key = pair[0].strip()
                value = pair[1].strip()
                if not key or not value:
                    continue
                if key == "Total":
                    value = value.replace(',', '')
                    event.add("count", value)
                elif key == "Last":
                    event.add("source time", value)
        event.add("feed", "projecthoneypot")
        event.add("type", "spam")

        return event

if __name__ == "__main__":
    ProjectHoneyPotBot.from_command_line().run()
