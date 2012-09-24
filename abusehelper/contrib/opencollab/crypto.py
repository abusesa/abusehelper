import sys
import hmac
import json
import struct
import hashlib
import subprocess

from binascii import hexlify
from random import SystemRandom
from base64 import b64decode, b64encode


random = SystemRandom()


def gen_salt(length):
    return "".join(chr(random.randint(0, 255)) for _ in xrange(length))


def pbkdf2(key, salt, hash_func=hashlib.sha256, iterations=4096, length=32):
    prf = _get_prf(hash_func)

    block_length = len(prf("", ""))
    block_count = length // block_length
    if block_length * block_count < length:
        block_count += 1

    result = "".join(_block(key, salt, prf, iterations, i + 1)
        for i in xrange(block_count))
    return result[:length]


def _get_prf(hash_func):
    return lambda key, msg: (hmac.new(key, msg, hash_func).digest())


def _xor(left, right):
    return "".join(chr(ord(l) ^ ord(r)) for (l, r) in zip(left, right))


def _block(key, salt, prf, iterations, i):
    result = prf(key, salt + struct.pack(">I", i))
    iteration = result

    for _ in xrange(iterations - 1):
        iteration = prf(key, iteration)
        result = _xor(result, iteration)

    return result


def _hmac256(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()


def _aes256(key, iv, data, encrypt=True):
    aes256 = subprocess.Popen(["openssl", "enc",
        "-e" if encrypt else "-d",
        "-aes-256-cbc", "-iv", hexlify(iv), "-K", hexlify(key)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    out, err = aes256.communicate(data)
    if aes256.wait() != 0:
        sys.stderr.write(err)
        sys.exit(aes256.returncode)
    return out


def crypt(data, password, iterations=2048):
    key_length = 32

    enc_salt = gen_salt(key_length)
    enc_key = pbkdf2(password, enc_salt, iterations=iterations, length=key_length)
    enc_iv = gen_salt(16)
    encrypted = _aes256(enc_key, enc_iv, data, True)

    hmac_salt = gen_salt(key_length)
    hmac_key = pbkdf2(password, hmac_salt, iterations=iterations, length=key_length)

    return json.dumps({
        "iterations": iterations,

        "aes256-cbc": {
            "salt": b64encode(enc_salt),
            "iv": b64encode(enc_iv),
            "data": b64encode(encrypted)
        },

        "hmac-sha256": {
            "salt": b64encode(hmac_salt),
            "data": b64encode(_hmac256(hmac_key, enc_iv + encrypted))
        }
    })


class DecryptionError(Exception):
    pass


def _validate(data, validations):
    result = dict()

    for key, value in validations.iteritems():
        if key not in data:
            raise DecryptionError("missing key {0!r}".format(key))

        if isinstance(value, dict):
            result[key] = _validate(data[key], value)
        else:
            try:
                result[key] = value(data[key])
            except (ValueError, TypeError):
                raise DecryptionError("could not validate key {0!r}".format(key))

    return result


def decrypt(data, password):
    try:
        data = json.loads(data)
    except ValueError:
        raise DecryptionError("not valid JSON data")

    data = _validate(data, {
        "iterations": int,

        "aes256-cbc": {
            "salt": b64decode,
            "iv": b64decode,
            "data": b64decode,
        },

        "hmac-sha256": {
            "salt": b64decode,
            "data": b64decode
        }
    })

    key_length = 32

    iterations = data["iterations"]
    encrypted = data["aes256-cbc"]["data"]
    iv = data["aes256-cbc"]["iv"]

    hmac_salt = data["hmac-sha256"]["salt"]
    hmac_key = pbkdf2(password, hmac_salt, iterations=iterations, length=key_length)
    if _hmac256(hmac_key, iv + encrypted) != data["hmac-sha256"]["data"]:
        raise DecryptionError("HMAC digest does not match")

    key_salt = data["aes256-cbc"]["salt"]
    key = pbkdf2(password, key_salt, iterations=iterations, length=key_length)

    plain = _aes256(key, iv, encrypted, False)
    return plain


if __name__ == "__main__":
    plaintext = sys.argv[1]
    password = sys.argv[2]

    enc = crypt(plaintext, password)
    print "encrypted:", enc
    print "decrypted:", decrypt(enc, password)
