import re
import json
import token
import tokenize
from StringIO import StringIO

from opencollab import wiki

import idiokit
from idiokit import timer
from abusehelper.core import bot, rules
from abusehelper.core.startup import Bot, StartupBot
from abusehelper.contrib.opencollab.crypto import decrypt, DecryptionError

TYPES = {"True":True, "true":True, "False":False, "false":False, "None":None,
         "none":None}

TOKENS = {"AND":rules.AND, "OR":rules.OR, "NOT":rules.NOT,
          "MATCH":rules.MATCH, "NETBLOCK":rules.NETBLOCK,
          "ANYTHING":rules.ANYTHING}

# Keys that are handled as a list in existing code should be lists
LIST_KEYS = ['resolve', 'asns']

def startswith(string, words):
    for word in words:
        if string.startswith(word):
            return True
    return False

def rmlink(value):
    if value.startswith("[[") and value.endswith("]]"):
        return value[2:-2]
    return value

def get_rule_tokens(string):
    tokens = list()
    rl = StringIO(string).readline
    try:
        for ttype, tstring, start, end, string in tokenize.generate_tokens(rl):
            if ttype == token.ENDMARKER:
                break
            elif ttype not in [token.NAME,token.OP,token.STRING,token.NUMBER]:
                return
            tokens.append((ttype, tstring))
    except tokenize.TokenError, e:
        return
    return tokens

def parse_rule(tokens):
    def find_args(tokens, end):
        args = list()
        while tokens[0][1] != end:
            parsed = parse_rule(tokens)
            if parsed:
                args.append(parsed)
        tokens.pop(0)
        return tokens, args

    ttype, tstring = tokens.pop(0)
    if ttype == token.NAME:
        if tstring in TOKENS:
            ttype, parenthesis = tokens.pop(0)
            tokens, args = find_args(tokens, ")")
            return TOKENS[tstring](*args)
        elif tstring == "re":
            ttype, parenthesis = tokens.pop(0)
            tokens, args = find_args(tokens, ")")
            args.append(re.U)
            return re.compile(*args)
    elif ttype == token.OP and tstring == "[":
        tokens, values = find_args(tokens, "]")
        return values
    elif ttype in [token.STRING, token.NUMBER]:
        try:
            tstring = int(tstring)
        except ValueError:
            if tstring.startswith('"') and tstring.endswith('"') or \
               tstring.startswith("'") and tstring.endswith("'"):
                tstring = tstring[1:-1]
        return tstring

class WikiConfigInterface:
    default_metas = dict()

    @idiokit.stream
    def configs(self):
        self.collab = wiki.GraphingWiki(self.collab_url,
            ssl_verify_cert=not self.collab_ignore_cert,
            ssl_ca_certs=self.collab_extra_ca_certs)

        self.collab.authenticate(self.collab_user, self.collab_password)

        while True:
            self.log.info("Reading configs")
            if getattr(self, "defaults_page", None):
                previous_defaults = self.default_metas.copy()
                pages = self.get_metas(self.defaults_page)
                for page, metas in pages.iteritems():
                    metas = self.parse_page(page, metas)
                    metas = self.parse_metas(metas)
                    self.default_metas.update(metas)
                if self.default_metas != previous_defaults:
                    self.log.info("Defaults values changed on page %r",
                                  self.defaults_page)
                
            pages = self.get_metas(self.category)
            if pages:
                bots = self.parse_pages(pages)
                if bots:
                    yield idiokit.send(bots)
            yield timer.sleep(self.poll_interval)

    def get_metas(self, query):
        try:
            pages = self.collab.getMeta(query)
        except wiki.WikiFailure as fail:
            self.log.error("getMeta failed: {0!r}".format(fail))
        else:
            return pages

    def get_content(self, page):
        self.log.info("Fetching page %s", page)
        try:
            content = self.collab.getPage(page)
            lines = content.split("\n")
            if len(lines) > 2:
                if lines[0].startswith("{{{") and lines[-1].endswith("}}}"):
                    content = "\n".join(lines[1:-1])
        except wiki.WikiFailure as fail:
            self.log.error("getPage failed: {0!r}".format(fail))
        else:
            return content

    def parse_metas(self, metas, skip=[]):
        for key, values in metas.iteritems():
            if not values or key in skip:
                continue

            values = list(values)
            for index, value in enumerate(values):
                if startswith(value, TOKENS.keys()):
                    try:
                        rules = parse_rule(get_rule_tokens(value))
                        values[index] = rules
                        continue
                    except (TypeError, AttributeError), e:
                        pass

                if value.startswith("[[") and value.endswith("]]"):
                    if key in ["room", "src_room", "dst_room"]:
                        content = rmlink(value)
                        if content:
                            values[index] = content
                    else:
                        content = self.get_content(rmlink(value))
                        if content:
                            values[index] = content
                        else:
                            try:
                                values[index] = json.loads(value)
                            except ValueError:
                                values[index] = value
                else:
                    try:
                        if self.decrypt_password:
                            values[index] = decrypt(value,
                                                    self.decrypt_password)
                        else:
                            values[index] = json.loads(value)
                    except (ValueError, DecryptionError, TypeError):
                        values[index] = value

            if len(values) == 1 and key not in LIST_KEYS:
                values = values[0]
            metas[key] = values

        return metas


class WikiStartupBot(WikiConfigInterface, StartupBot):
    collab_url = bot.Param("Collab url")
    collab_user = bot.Param("Collab user")
    collab_password = bot.Param("Collab password", default=None)
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)

    category = bot.Param("Page category (default: %default)",
                         default="CategoryBot")
    defaults_page = bot.Param("Page for default values for bot arguments", 
                              default=None)
    poll_interval = bot.IntParam("how often (in seconds) the collab is " +
                                 "checked for updates (default: %default)",
                                 default=60)
    decrypt_password = bot.Param("Password for decrypting metas.", default=None)

    xmpp_jid = bot.Param("the XMPP JID (e.g. xmppuser@xmpp.example.com)",
        default=None)
    xmpp_password = bot.Param("the XMPP password",
        default="")
    xmpp_host = bot.Param("the XMPP service host (default: autodetect)",
        default=None)
    xmpp_port = bot.IntParam("the XMPP service port (default: autodetect)",
        default=None)
    xmpp_extra_ca_certs = bot.Param("""
        a PEM formatted file of CAs to be used in addition to the system CAs
        """, default=None)
    xmpp_ignore_cert = bot.BoolParam("""
        do not perform any verification for the XMPP service's SSL certificate
        """, default=None)

    def __init__(self, *args, **keys):
        super(WikiStartupBot, self).__init__(*args, **keys)
        self.collab = None
        self._metas = dict()

    def parse_page(self, page, metas):
        metas = dict(metas)
        for key in ['gwikilabel', 'gwikicategory']:
            try:
                del metas[key]
            except KeyError:
                pass

        keys = ["xmpp_jid", "xmpp_password", "xmpp_host", "xmpp_port",
                "xmpp_extra_ca_certs", "xmpp_ignore_cert"]
        for key in keys:
            value = list(metas.get(key, set()))
            if not value:
                default = getattr(self, key, None)
                if default is not None:
                    metas[key] = set([unicode(default)])

        return metas

    def parse_pages(self, pages):
        bots = list()

        for page, metas in pages.iteritems():
            metas = self.parse_page(page, metas)

            name = list(metas.pop("name", set()))
            if not name:
                self.log.error('%s: Missing name.', page)
                return
            elif len(name) > 1:
                self.log.error("%s: Too many values for name.", page)
                return
            else:
                name = rmlink(name[0])

            module = list(metas.pop("module", set()))
            if not module:
                module = None
            elif len(module) > 1:
                self.log.error("%s: Too many values for module.", page)
                return
            elif len(module) == 1:
                module = rmlink(module[0])

            enable = list(metas.pop("enabled", set()))
            if enable:
                val = enable[0]
                if val in TYPES and not TYPES[val]:
                    continue

            pages[page] = self.parse_metas(metas)

            for key in self.default_metas:
                if not key in metas:
                    metas[key] = self.default_metas[key]

            if module:
                bots.append(Bot(name, module, **metas))
            else:
                bots.append(Bot(name, **metas))

        if pages != self._metas:
            self._metas = pages
            return bots

if __name__ == "__main__":
    WikiStartupBot.from_command_line().execute()
