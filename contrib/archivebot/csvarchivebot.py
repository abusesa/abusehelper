import os
import csv

from idiokit import threado
from abusehelper.core import bot

import archivebot

class CSVArchiveBot(archivebot.ArchiveBot):
    csv_columns = bot.ListParam()

    @threado.stream
    def collect(inner, self, room_name):
        room_name = unicode(room_name).encode("utf-8")
        archive = open(os.path.join(self.archive_dir, room_name), "ab")
        csvfile = csv.writer(archive)

        try:
            if archive.tell() == 0:
                csvfile.writerow([x.encode("utf-8") for x in self.csv_columns])

            while True:
                event = yield inner

                row = list()
                for column in self.csv_columns:
                    value = event.value(column, u"").encode("utf-8")
                    row.append(value)
                csvfile.writerow(row)
                archive.flush()
        finally:
            archive.flush()
            archive.close()

if __name__ == "__main__":
    CSVArchiveBot.from_command_line().execute()
