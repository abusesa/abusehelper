import time
import idiokit
from abusehelper.core import bot, utils


COLUMNS = ("first seen", "threat", "malware", "host", "url", "status", "registrar", "ip", "asn", "cc")


def _value_split(values):
    results = set()
    for value in values:
        results = results | set([x for x in value.split("|") if x])
    return tuple(results)


@idiokit.stream
def _parse():
    while True:
        event = yield idiokit.next()

        for key in event.keys():
            event.pop(key, filter=lambda value: not value.strip())

        for key in ("ip", "asn", "cc"):
            event.update(key, _value_split(event.pop(key)))

        for timestamp in event.pop("first seen"):
            try:
                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%SZ",
                    time.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                )
            except ValueError:
                pass
            else:
                event.add("first seen", timestamp)

        yield idiokit.send(event)


class RansomwareTrackerBot(bot.PollingBot):
    feed_url = bot.Param(default="https://ransomwaretracker.abuse.ch/feeds/csv/")

    @idiokit.stream
    def poll(self):
        self.log.info("Downloading {0}".format(self.feed_url))
        try:
            info, fileobj = yield utils.fetch_url(self.feed_url)
        except utils.FetchUrlFailed as fuf:
            raise bot.PollSkipped("Download failed: {0}".format(fuf))

        lines = []
        for line in fileobj:
            line = line.strip()

            if line and not line.startswith("#"):
                lines.append(line)

        yield idiokit.pipe(
            utils.csv_to_events(tuple(lines),
                                columns=COLUMNS,
                                charset=info.get_param("charset", None)),
            _parse()
        )

if __name__ == "__main__":
    RansomwareTrackerBot.from_command_line().execute()
