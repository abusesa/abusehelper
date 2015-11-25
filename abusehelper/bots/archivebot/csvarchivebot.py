import csv
from abusehelper.core import bot, archivebot


class CSVArchiveBot(archivebot.ArchiveBot):
    csv_columns = bot.ListParam()

    def archive_path(self, *args, **keys):
        path = archivebot.ArchiveBot.archive_path(self, *args, **keys)
        path += ".csv"
        return path

    def archive_open(self, archive_path):
        archive = open(archive_path, "ab")
        try:
            csvfile = csv.writer(archive)

            if archive.tell() == 0:
                csvfile.writerow([x.encode("utf-8") for x in self.csv_columns])
        except:
            archive.close()
            raise

        return archive, csvfile

    def archive_write(self, (_, csvfile), timestamp, room_name, event):
        row = list()
        for column in self.csv_columns:
            value = event.value(column, u"").encode("utf-8")
            row.append(value)
        csvfile.writerow(row)

    def archive_flush(self, (archive, _)):
        archive.flush()

    def archive_close(self, (archive, _)):
        archive.close()

if __name__ == "__main__":
    CSVArchiveBot.from_command_line().execute()
