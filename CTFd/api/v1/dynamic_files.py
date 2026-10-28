import re
import time

from flask import request
from flask_restx import Namespace, Resource

from CTFd.cache import clear_challenges
from CTFd.dynamic_files import GeneratorError, fetch
from CTFd.models import Challenges, DynamicFiles, Teams, Users, db
from CTFd.plugins.flags import dynamic
from CTFd.utils.decorators import admins_only

dynamic_files_namespace = Namespace(
    "dynamic_files", description="Endpoint to manage per-team challenge files"
)

FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FIELDS = ("challenge_id", "filename", "endpoint", "secret", "bind", "timeout")


def dump(df):
    return {k: getattr(df, k) for k in ("id",) + FIELDS}


def clean(req, partial=False):
    """Validate a create/patch body. Returns (data, errors)."""
    data, errors = {}, {}
    req = {k: v for k, v in (req or {}).items() if k in FIELDS}
    if not partial:
        for k in ("challenge_id", "filename", "endpoint"):
            if not req.get(k):
                errors[k] = ["Required"]

    if "challenge_id" in req and req["challenge_id"]:
        if Challenges.query.filter_by(id=req["challenge_id"]).first() is None:
            errors["challenge_id"] = ["No such challenge"]
        else:
            data["challenge_id"] = int(req["challenge_id"])

    if req.get("filename"):
        name = str(req["filename"]).strip()
        if FILENAME_RE.match(name):
            data["filename"] = name
        else:
            errors["filename"] = ["Use letters, digits, dot, dash or underscore"]

    if req.get("endpoint"):
        url = str(req["endpoint"]).strip()
        if url.startswith(("http://", "https://")):
            data["endpoint"] = url
        else:
            errors["endpoint"] = ["Must start with http:// or https://"]

    if "secret" in req:
        secret = (req["secret"] or "").strip().lower()
        if not secret:
            if not partial:
                data["secret"] = dynamic.new_secret()
        elif dynamic.is_valid_secret(secret):
            data["secret"] = secret
        else:
            errors["secret"] = ["Secret must be hex (0-9, a-f)"]
    elif not partial:
        data["secret"] = dynamic.new_secret()

    if req.get("bind"):
        if req["bind"] in dynamic.BINDS:
            data["bind"] = req["bind"]
        else:
            errors["bind"] = [f"One of {', '.join(dynamic.BINDS)}"]

    if req.get("timeout") not in (None, ""):
        try:
            timeout = int(req["timeout"])
            if not 1 <= timeout <= 600:
                raise ValueError
            data["timeout"] = timeout
        except (TypeError, ValueError):
            errors["timeout"] = ["Seconds between 1 and 600"]

    return data, errors


@dynamic_files_namespace.route("")
class DynamicFileList(Resource):
    @admins_only
    def get(self):
        q = DynamicFiles.query
        challenge_id = request.args.get("challenge_id", type=int)
        if challenge_id is not None:
            q = q.filter_by(challenge_id=challenge_id)
        return {"success": True, "data": [dump(df) for df in q.all()]}

    @admins_only
    def post(self):
        data, errors = clean(request.get_json())
        if errors:
            return {"success": False, "errors": errors}, 400
        df = DynamicFiles(**data)
        db.session.add(df)
        db.session.commit()
        response = dump(df)
        db.session.close()
        clear_challenges()
        return {"success": True, "data": response}


@dynamic_files_namespace.route("/<int:file_id>")
@dynamic_files_namespace.param("file_id", "A DynamicFile ID")
class DynamicFile(Resource):
    @admins_only
    def get(self, file_id):
        df = DynamicFiles.query.filter_by(id=file_id).first_or_404()
        return {"success": True, "data": dump(df)}

    @admins_only
    def patch(self, file_id):
        df = DynamicFiles.query.filter_by(id=file_id).first_or_404()
        data, errors = clean(request.get_json(), partial=True)
        if errors:
            return {"success": False, "errors": errors}, 400
        for k, v in data.items():
            setattr(df, k, v)
        db.session.commit()
        response = dump(df)
        db.session.close()
        clear_challenges()
        return {"success": True, "data": response}

    @admins_only
    def delete(self, file_id):
        df = DynamicFiles.query.filter_by(id=file_id).first_or_404()
        db.session.delete(df)
        db.session.commit()
        db.session.close()
        clear_challenges()
        return {"success": True}


@dynamic_files_namespace.route("/<int:file_id>/test")
@dynamic_files_namespace.param("file_id", "A DynamicFile ID")
class DynamicFileTest(Resource):
    @admins_only
    def get(self, file_id):
        """Fetch the file once as ?team=<name> and report what came back."""
        df = DynamicFiles.query.filter_by(id=file_id).first_or_404()
        name = (request.args.get("team") or "").strip()
        if not name:
            return {"success": False, "errors": {"team": ["Required"]}}, 400

        team = Teams.query.filter_by(name=name).first()
        user = Users.query.filter_by(name=name).first()
        team_id = str(team.id) if team else ""
        user_id = str(user.id) if user else ""

        start = time.monotonic()
        try:
            r = fetch(df, name, team_id, user_id)
        except GeneratorError as e:
            return {"success": False, "errors": {"generator": [str(e)]}}, 502
        try:
            size = sum(len(c) for c in r.iter_content(64 * 1024))
        finally:
            r.close()
        return {
            "success": True,
            "data": {
                "status": r.status_code,
                "content_type": r.headers.get("Content-Type"),
                "bytes": size,
                "seconds": round(time.monotonic() - start, 2),
            },
        }
