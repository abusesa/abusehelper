import abusechbot

class ZeuSTrackerBot(abusechbot.AbuseCHBot):
    malware = "zeus"

    types = {
        "c&c": "https://zeustracker.abuse.ch/rss.php",
        "config": "https://zeustracker.abuse.ch/monitor.php?urlfeed=configs",
        "binary": "https://zeustracker.abuse.ch/monitor.php?urlfeed=binaries",
        "dropzone": "https://zeustracker.abuse.ch/monitor.php?urlfeed=dropzones"
    }

if __name__ == "__main__":
    ZeuSTrackerBot.from_command_line().execute()
