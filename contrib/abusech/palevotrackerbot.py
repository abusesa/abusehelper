import abusechbot

class PalevoTrackerBot(abusechbot.AbuseCHBot):
    malware = "palevo"

    types = {
        "c&c": "http://amada.abuse.ch/palevotracker.php?rssfeed"
    }

if __name__ == "__main__":
    PalevoTrackerBot.from_command_line().execute()
