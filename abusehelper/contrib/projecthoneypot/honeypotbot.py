"""
Project Honeypot feed handler.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

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
        title = keys.get("title").split(' | ')
        if len(title) == 2:
            ip, types = title
            if types == "Se":
                return None
            items = []
            for item in descriptions:
                if item in types:
                    items.append(descriptions[item])
            if len(items) > 0:
                desc = "This host is most likely part of SPAM infrastructure as: " + \
                    ", ".join(items) + "."
                event.add('description', desc)
            if ip:
                url = "http://www.projecthoneypot.org/ip_" + ip
                event.add("description url", url)
                event.add("ip", ip)
            else:
                # events should always contain an ip
                # drop the event if it does not
                return None
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
