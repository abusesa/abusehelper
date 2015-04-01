import os
import re
import sys
import shutil
import getpass
from idiokit.xmpp import jid

NOT_GIVEN = object()

def input(name, default=NOT_GIVEN, parser=NOT_GIVEN):
    while True:
        result = raw_input(name + ": ").strip()
        if not result:
            if default is NOT_GIVEN:
                continue
            return default

        if parser is NOT_GIVEN:
            return result

        try:
            return parser(result)
        except Exception, error:
            print >> sys.stderr, "Invalid value:", error

def password(name):
    while True:
        result = getpass.getpass(name + ": ")
        if not result:
            continue

        while True:
            repeated = getpass.getpass(name + " (again): ")
            if not repeated:
                continue

            if repeated == result:
                return result

            print >> sys.stderr, "Passwords do not match"
            break

def replace(string, values):
    sub = lambda match: repr(values[match.group(2).strip()])
    return re.sub(r"(?P<open>[\"\'])@(.*?)@(?P=open)", sub, string)

def parse_jid(string):
    value = jid.JID(string)
    if value.node is None:
        raise jid.JIDError("JID has to be of form node@domain")

    value = unicode(value)
    try:
        return str(value)
    except UnicodeDecodeError:
        return value

def parse_yes_no(string):
    string = string.lower()
    if string in ("y", "ye", "yes"):
        return True
    if string in ("n", "no"):
        return False
    raise ValueError("answer either yes or no")

def generate(dst):
    dirname = os.path.dirname(__file__)
    src = os.path.join(dirname, "config-template")

    try:
        shutil.copytree(src, dst)
        try:
            replaces = dict(XMPP_JID=input("XMPP username", parser=parse_jid),
                            XMPP_PASSWORD=password("XMPP password"),
                            SERVICE_ROOM=input("XMPP lobby channel"))

            if input("Configure mailer? yes/[no]", False, parse_yes_no):
                replaces.update(ENABLE_MAILER=True,
                                SMTP_HOST=input("SMTP host"),
                                SMTP_PORT=input("SMTP port [25]", 25, int))

                smtp_auth_user = input("SMTP auth user [no auth]", None)
                if smtp_auth_user is None:
                    smtp_auth_user = None
                    smtp_auth_password = None
                else:
                    smtp_auth_password = password("SMTP auth password")

                replaces.update(SMTP_AUTH_USER=smtp_auth_user,
                                SMTP_AUTH_PASSWORD=smtp_auth_password,
                                MAIL_SENDER=input("Mail sender"))
            else:
                replaces.update(ENABLE_MAILER=False,
                                SMTP_HOST="mail.example.com",
                                SMTP_PORT=25,
                                SMTP_AUTH_USER=None,
                                SMTP_AUTH_PASSWORD=None,
                                MAIL_SENDER="sender@example.com")

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

def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, "USAGE:", sys.executable, sys.argv[0], "CONFIGDIR"
        sys.exit(1)
    generate(sys.argv[1])

if __name__ == "__main__":
    main()
