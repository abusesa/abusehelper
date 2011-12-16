# -*- coding: utf-8 -*-
"""
    Mailer that does PGP signing and encryption. Needs pyme and
    handling the PGP key store for the user that runs the bot.
"""
__authors__ = "Jussi Eronen and Joachim Viide"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import pyme.core
try:
    import pyme.pygpgme as gpgme
except ImportError:
    import pyme.gpgme as gpgme

from idiokit import threado
from abusehelper.core import mailer, bot
from email.mime.text import MIMEText

def get_valid_keys(ctx, patterns=[], sign=0):
    keys = []
    for pattern in patterns:
        keys.extend(key for key in ctx.op_keylist_all(pattern, sign)
                    if (key.can_encrypt != 0))
    return keys

# Sign and encrypt as much as it is possible
def sign_and_encrypt(data, sign_key='', passphrase='', 
                     send_to=[], own_key='', attachment=False):

    ctx = pyme.core.Context()
    ctx.set_armor(1)

    plaintext = pyme.core.Data(data)
    encrypted = pyme.core.Data()

    recipients = get_valid_keys(ctx, send_to)

    if recipients:
        recipients.extend(get_valid_keys(ctx, [own_key]))

    if sign_key:
        ctx.signers_add(sign_key)
        ctx.set_passphrase_cb(lambda *args, **kw: passphrase)

    if sign_key and passphrase and recipients:
        # http://pyme.sourceforge.net/doc/gpgme/Encrypting-a-Plaintext.html
        # The 1 is gpgme_encrypt_flags_t for GPGME_ENCRYPT_ALWAYS_TRUST
        ctx.op_encrypt_sign(recipients, 1, plaintext, encrypted)
    elif sign_key and passphrase:
        if attachment:
            mode = pyme.pygpgme.GPGME_SIG_MODE_DETACH
        else:
            mode = pyme.pygpgme.GPGME_SIG_MODE_CLEAR

        ctx.op_sign(plaintext, encrypted, mode)
    elif recipients:
        ctx.op_encrypt(recipients, 1, plaintext, encrypted)
    else:
        return data, ''

    encrypted.seek(0, 0)
    enc_data = encrypted.read()

    # Detach sig
    if attachment and not recipients:
        return enc_data, data

    return enc_data, ''

class Mailer(mailer.MailerService):
    sign_keys = bot.ListParam("PGP signing key ids", default=None)
    passphrase = bot.Param("PGP signing key passphrase", default=None)

    @threado.stream
    def build_mail(inner, self, _events, template="", 
                   to=[], cc=[], keywords=(), **keys):

        if not self.sign_keys or not self.passphrase:
            inner.finish(msg)

        # Sign mail
        msgparts = msg.walk()
        msgparts.next()

        ctx = pyme.core.Context()
        ctx.set_armor(1)
        sign_key = get_valid_keys(ctx, self.sign_keys, sign=1)
        if sign_key:
            sign_key = sign_key[0]
        else:
            inner.finish(msg)

        newparts = list()

        for i, part in enumerate(msgparts):
            # Sign message body
            if i == 0:
                data = part.get_payload(decode=True)
                data = sign_and_encrypt(data, sign_key, self.passphrase)[0]
                part.set_payload(data.encode('base64'))
            else:
                fname = part.get_filename()
                data = part.get_payload(decode=True)
                sig = sign_and_encrypt(data, sign_key, self.passphrase,
                                       attachment=True)[0]

                newpart = MIMEText(sig, 'application/pgp-signature', "utf-8")
                newpart.add_header("Content-Disposition", "attachment", 
                                   filename=fname + '.asc')

                newparts.append(newpart)

        for part in newparts:
            msg.attach(part)

        inner.finish(msg)

if __name__ == "__main__":
    Mailer.from_command_line().execute()
