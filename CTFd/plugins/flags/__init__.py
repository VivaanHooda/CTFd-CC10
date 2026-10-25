import hmac
import json
import logging
import re

from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.flags import dynamic

log = logging.getLogger(__name__)


class FlagException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class BaseFlag(object):
    name = None
    templates = {}

    @staticmethod
    def compare(self, saved, provided):
        return True


class CTFdStaticFlag(BaseFlag):
    name = "static"
    templates = {  # Nunjucks templates used for key editing & viewing
        "create": "/plugins/flags/assets/static/create.html",
        "update": "/plugins/flags/assets/static/edit.html",
    }

    @staticmethod
    def compare(chal_key_obj, provided):
        saved = chal_key_obj.content
        data = chal_key_obj.data

        if len(saved) != len(provided):
            return False
        result = 0

        if data == "case_insensitive":
            for x, y in zip(saved.lower(), provided.lower()):
                result |= ord(x) ^ ord(y)
        else:
            for x, y in zip(saved, provided):
                result |= ord(x) ^ ord(y)
        return result == 0


class CTFdRegexFlag(BaseFlag):
    name = "regex"
    templates = {  # Nunjucks templates used for key editing & viewing
        "create": "/plugins/flags/assets/regex/create.html",
        "update": "/plugins/flags/assets/regex/edit.html",
    }

    @staticmethod
    def compare(chal_key_obj, provided):
        saved = chal_key_obj.content
        data = chal_key_obj.data

        try:
            if data == "case_insensitive":
                res = re.match(saved, provided, re.IGNORECASE)
            else:
                res = re.match(saved, provided)
        # TODO: this needs plugin improvements. See #1425.
        except re.error as e:
            raise FlagException("Regex parse error occured") from e

        return res and res.group() == provided


class CTFdDynamicFlag(BaseFlag):
    """
    Per-team flag. content is the base flag (e.g. cc10{w4x}); data is JSON
    {"secret": hex, "len": 10, "bind": "team_name"}. Each team must submit the
    base flag with its own HMAC tag inserted (see dynamic.py).
    """

    name = "dynamic"
    templates = {  # Nunjucks templates used for key editing & viewing
        "create": "/plugins/flags/assets/dynamic/create.html",
        "update": "/plugins/flags/assets/dynamic/edit.html",
    }

    @staticmethod
    def prepare_data(data):
        """
        Normalise the data JSON for a dynamic flag before it is saved.
        Generates a secret when none is given. Raises FlagException on bad input.
        """
        if isinstance(data, str):
            try:
                data = json.loads(data) if data.strip() else {}
            except ValueError:
                raise FlagException("Dynamic flag data must be JSON")
        if not isinstance(data, dict):
            raise FlagException("Dynamic flag data must be a JSON object")

        secret = (data.get("secret") or "").strip().lower()
        if not secret:
            secret = dynamic.new_secret()
        elif not dynamic.is_valid_secret(secret):
            raise FlagException("Secret key must be hex (0-9, a-f)")

        try:
            length = int(data.get("len") or dynamic.DEFAULT_LENGTH)
        except (ValueError, TypeError):
            raise FlagException("Tag length must be a number")
        if not 4 <= length <= 64:
            raise FlagException("Tag length must be between 4 and 64")

        bind = data.get("bind") or "team_name"
        if bind not in dynamic.BINDS:
            raise FlagException(f"bind must be one of {', '.join(dynamic.BINDS)}")

        return json.dumps({"secret": secret, "len": length, "bind": bind})

    @staticmethod
    def expected(chal_key_obj, identity):
        cfg = json.loads(chal_key_obj.data)
        return dynamic.make_flag(
            cfg["secret"],
            identity,
            chal_key_obj.content,
            int(cfg.get("len", dynamic.DEFAULT_LENGTH)),
        )

    @staticmethod
    def identity(bind):
        from CTFd.utils.user import get_current_team, get_current_user

        team = get_current_team()
        user = get_current_user()
        if bind == "team_id":
            return str(team.id) if team else None
        if bind == "user_id":
            return str(user.id) if user else None
        if bind == "user_name":
            return user.name if user else None
        # team_name, falling back to the user's name in user mode
        if team:
            return team.name
        return user.name if user else None

    @staticmethod
    def compare(chal_key_obj, provided):
        # Never raise here: a broken flag must reject, not 500 the submission
        try:
            bind = json.loads(chal_key_obj.data).get("bind", "team_name")
            identity = CTFdDynamicFlag.identity(bind)
            if not identity:
                return False
            expected = CTFdDynamicFlag.expected(chal_key_obj, identity)
        except Exception:
            log.exception(
                "Dynamic flag %s is misconfigured", getattr(chal_key_obj, "id", "?")
            )
            return False
        return hmac.compare_digest(provided.strip(), expected)


FLAG_CLASSES = {
    "static": CTFdStaticFlag,
    "regex": CTFdRegexFlag,
    "dynamic": CTFdDynamicFlag,
}


def get_flag_class(class_id):
    cls = FLAG_CLASSES.get(class_id)
    if cls is None:
        raise KeyError
    return cls


def load(app):
    register_plugin_assets_directory(app, base_path="/plugins/flags/assets/")
