# A bot that launches other bots (Python modules, really) based on INI
# file sections. Section options are passed as startup parameters to
# the bot, except for the module option, which is used to determine
# the module/file which will be run.
#
# The bot supports the INI format accepted by the
# ConfigParser.SafeConfigParser class in the Python standard library,
# documented in http://docs.python.org/library/configparser.html. As
# an useful addition for defining paths relative to the INI file, the
# bot defines an additional string interpolation constant __dir__
# pointing to the INI file's own directory.

import os
from abusehelper.core import bot, startup, config
from ConfigParser import SafeConfigParser

class ConfigParser(SafeConfigParser):
    def __init__(self, filename):
        filename = os.path.abspath(filename)
        directory, _ = os.path.split(filename)
        SafeConfigParser.__init__(self, dict(__dir__=directory))

        opened = open(filename, "r")
        try:
            self.readfp(opened)
        finally:
            opened.close() 

class ConfigObj(object):
    def __init__(self, params):
        self.params = params

    def startup(self):
        return self.params

class INIStartupBot(startup.StartupBot):
    ini_file = bot.Param("configuration INI file")
    enable = bot.ListParam("bots that are run (default: run all bots)",
                           default=None)
    disable = bot.ListParam("bots that are not run (default: run all bots)", 
                            default=None)

    def configs(self):
        ini_file = ConfigParser(self.ini_file)

        for section in ini_file.sections():
            params = dict(ini_file.items(section))

            names = set([section, params["bot_name"], params["module"]])
            if self.disable is not None and names & set(self.disable):
                continue
            if self.enable is not None and not (names & set(self.enable)):
                continue

            yield ConfigObj(params)

if __name__ == "__main__":
    INIStartupBot.from_command_line().execute()
