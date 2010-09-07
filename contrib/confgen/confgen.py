from __future__ import with_statement
import os
import re
import sys
import shutil
from idiokit import jid

def dummy(_repr):
    class _dummy(object):
        def __repr__(self):
            return _repr
    return _dummy()

NOT_GIVEN = dummy("<not given>")

def input(name, default=NOT_GIVEN, parser=NOT_GIVEN):
    prompt = name
    if default is not NOT_GIVEN:
        prompt += " [" + repr(default) + "]"
    prompt += ": "

    while True:
        result = raw_input(prompt).strip()
        if not result:
            if default is NOT_GIVEN:
                continue
            return default

        if parser is NOT_GIVEN:
            return result

        try:
            return parser(result)
        except Exception, error:
            print >> sys.stderr, "Invalid value for " + name + ":", error

def replace(string, values):
    replace_rex = "(?P<open>[\"\'])@(.*?)@(?P=open)"
    def _sub(match):
        return repr(values[match.group(2).strip()])
    return re.sub(replace_rex, _sub, string)

def parse_jid(string):
    value = jid.JID(string)
    if value.node is None:
        raise jid.JIDError("JID has to be of form node@domain")

    value = unicode(value)
    try:
        return str(value)
    except UnicodeDecodeError:
        return value

dirname = os.path.dirname(__file__)

if len(sys.argv) != 2:
    print >> sys.stderr, "USAGE:", sys.argv[0], "CONFIGDIR"
    sys.exit(1)

src = os.path.join(dirname, "config-template")
dst = sys.argv[1]

try:
    shutil.copytree(src, dst)
    try:
        replaces = dict(XMPP_JID=input("XMPP username", parser=parse_jid),
                        XMPP_PASSWORD=input("XMPP password"),
                        SERVICE_ROOM=input("Lobby"),
                        SMTP_HOST=input("SMTP host"),
                        SMTP_PORT=input("SMTP port", 25, int))

        no_auth = dummy("no auth")
        smtp_auth_user = input("SMTP auth user", no_auth)
        if smtp_auth_user is no_auth:
            smtp_auth_user = None
            smtp_auth_password = None
        else:
            smtp_auth_password = input("SMTP auth password")

        replaces.update(SMTP_AUTH_USER=smtp_auth_user,
                        SMTP_AUTH_PASSWORD=smtp_auth_password,
                        MAIL_SENDER=input("Mail sender"))
        
        with open(os.path.join(dst, "startup.py"), "r+") as startup_file:
            startup = replace(startup_file.read(), replaces)

            startup_file.seek(0)
            startup_file.truncate(0)
            startup_file.write(startup)
    except:
        shutil.rmtree(dst)
        raise
except Exception, error:
    print >> sys.stderr, "ERROR:", error
    sys.exit(1)
