from abusehelper.core import events
from abusehelper.contrib.tailbot.tailbot import TailBot

class SnortBot(TailBot):

    def parse(self, line):
        if not line:
            return 

        parts = line.split("]")
        if len(parts) < 4:
            return

        info = parts[1].split("[")
        if len(info) < 2:
            return

        network = parts[3].split(" ")
        if len(network) < 5:
            return

        event = events.Event()
        event.add("source", "snort")

        event.add("description", info[0].strip())
        event.add("classification", info[1].split(": ")[-1])
        event.add("priority", parts[2].strip(" [").split(": ")[-1])

        src = network[2].split(":")
        if len(src) > 1:
            event.add("src_addr", src[0])
            event.add("src_port", src[1])

        dst = network[4].split(":")
        if len(dst) > 1:
            event.add("dst_addr", dst[0])
            event.add("dst_port", dst[1])

        return event

if __name__ == "__main__":
    SnortBot.from_command_line().execute()

