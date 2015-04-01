import json
import getpass
import os
import sys

from abusehelper.core import bot, config
from abusehelper.bots.opencollab.crypto import decrypt, DecryptionError
from abusehelper.bots.opencollab.wikistartup import WikiStartupBot

def redirected(func, *args, **keys):
    oldStdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        return func(*args, **keys)
    finally:
        sys.stdout = oldStdout

class CryptoStartupBot(WikiStartupBot):
    cryptofile = bot.Param("""crypto credentials, json file crypted
    with crypto.py. Example json file:
    {"xmpp_password": "x", "collab_password": "x"}""")

    def run(self):
        if not os.path.isfile(self.cryptofile):
            raise bot.ParamError("No such file: " + repr(self.cryptofile))
        try:
            value = file(self.cryptofile, 'rb').read()
        except IOError: 
            raise bot.ParamError("Error reading file: " + repr(self.cryptofile))

        self.decrypt_password = redirected(getpass.getpass, "Password: ")
        try:
            data = decrypt(value, self.decrypt_password)
        except DecryptionError:
            raise bot.ParamError("Decryption error in: " + 
                                 repr(self.cryptofile))
        try:
            jsondata = json.loads(data)
        except (ValueError, TypeError):
            raise bot.ParamError("Error in json data in file: " +
                                 repr(self.cryptofile))
        for key, value in jsondata.iteritems():
            setattr(self, key, value)

        super(CryptoStartupBot, self).run()

if __name__ == '__main__':
    CryptoStartupBot.from_command_line().execute()
