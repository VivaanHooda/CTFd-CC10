"""
Dynamic (per-team) flag algorithm. Stdlib only, so challenge generators can
copy this file and mint exactly the flags CTFd will accept.

    tag  = HMAC-SHA256(secret, normalise(identity))[:length]   (lowercase hex)
    flag = base with tag inserted:
             - at %TAG% if the base contains it
             - else before the last "}" joined with "_"   cc10{x} -> cc10{x_<tag>}
             - else appended as "_<tag>"

Matches the legacy rvce_flags scheme with salt="" (each flag has its own secret).
"""

import hashlib
import hmac
import re
import secrets
import unicodedata

TAG = "%TAG%"
DEFAULT_LENGTH = 10
BINDS = ("team_name", "team_id", "user_name", "user_id")


def normalise(name):
    name = unicodedata.normalize("NFKC", name or "").casefold().strip()
    return re.sub(r"\s+", " ", name)


def new_secret():
    return secrets.token_hex(32)


def is_valid_secret(secret):
    try:
        return bool(secret) and len(bytes.fromhex(secret)) > 0
    except (ValueError, TypeError):
        return False


def make_tag(secret, identity, length=DEFAULT_LENGTH):
    key = bytes.fromhex(secret.strip())
    msg = normalise(identity).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:length]


def place_tag(base, tag):
    if TAG in base:
        return base.replace(TAG, tag)
    i = base.rfind("}")
    if i == -1:
        return f"{base}_{tag}"
    return f"{base[:i]}_{tag}{base[i:]}"


def make_flag(secret, identity, base, length=DEFAULT_LENGTH):
    return place_tag(base, make_tag(secret, identity, length))
