import abusechbot

class SpyEyeTrackerBot(abusechbot.AbuseCHBot):
    malware = "spyeye"

    types = {
        "c&c": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
        "config": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=configurls",
        "binary": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=binaryurls",
        "dropzone": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=dropurls"
    }

if __name__ == "__main__":
    SpyEyeTrackerBot.from_command_line().execute()
