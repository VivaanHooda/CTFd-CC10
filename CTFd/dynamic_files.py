"""
Per-team ("dynamic") challenge files.

The challenge modal shows a dynamic file as an ordinary file pill. Clicking it
hits /files/dynamic/<id>/<filename>; CTFd works out the team from the session,
calls the challenge's generator with a signed request and streams the file back.
Teams never see the generator URL and cannot ask for another team's file.

Signed request (generators verify it with ctfd_dl.py):

    GET <endpoint>?team=<identity>&team_id=<id>&user_id=<id>&ts=<unix>&sig=<hex>
    sig = HMAC-SHA256(secret, "ctfd-dl\\0" + team + "\\0" + team_id + "\\0"
                              + user_id + "\\0" + ts)
"""

import hashlib
import hmac
import logging
import time

import requests
from flask import Blueprint, Response, abort, stream_with_context

from CTFd.models import DynamicFiles, Solves
from CTFd.plugins.flags import CTFdDynamicFlag
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import (
    authed_only,
    during_ctf_time_only,
    require_verified_emails,
)
from CTFd.utils.decorators.visibility import check_challenge_visibility
from CTFd.utils.logging import log
from CTFd.utils.modules import can_access_challenge
from CTFd.utils.user import get_current_team, get_current_user, is_admin

dynamic_files = Blueprint("dynamic_files", __name__)

logger = logging.getLogger(__name__)

CHUNK = 64 * 1024
DOMAIN = "ctfd-dl"


class GeneratorError(Exception):
    pass


def sign(secret, team, team_id, user_id, ts):
    msg = "\0".join([DOMAIN, team, team_id, user_id, ts]).encode()
    return hmac.new(bytes.fromhex(secret), msg, hashlib.sha256).hexdigest()


def fetch(df, team, team_id, user_id):
    """
    Ask the generator for team's file. Returns an open streaming response;
    the caller must close it. Raises GeneratorError on any failure.
    """
    ts = str(int(time.time()))
    params = {
        "team": team,
        "team_id": team_id,
        "user_id": user_id,
        "ts": ts,
        "sig": sign(df.secret, team, team_id, user_id, ts),
    }
    try:
        r = requests.get(
            df.endpoint,
            params=params,
            stream=True,
            timeout=(5, df.timeout or 60),
            allow_redirects=False,
        )
    except requests.RequestException as e:
        raise GeneratorError(f"generator unreachable: {e}") from e
    if r.status_code != 200:
        r.close()
        raise GeneratorError(f"generator returned HTTP {r.status_code}")
    return r


def unlocked(challenge, user):
    """Prerequisites solved (or none). Mirrors the challenge API check."""
    prereqs = (challenge.requirements or {}).get("prerequisites", [])
    if not prereqs:
        return True
    solved = {
        cid
        for (cid,) in Solves.query.with_entities(Solves.challenge_id).filter_by(
            account_id=user.account_id
        )
    }
    return set(prereqs) <= solved


@dynamic_files.route("/files/dynamic/<int:file_id>/<filename>")
@authed_only
@check_challenge_visibility
@during_ctf_time_only
@require_verified_emails
def download(file_id, filename):
    df = DynamicFiles.query.filter_by(id=file_id).first_or_404()
    chal = df.challenge
    user = get_current_user()
    team = get_current_team()

    if not is_admin():
        if chal.state in ("hidden", "locked"):
            abort(404)
        if not can_access_challenge(chal, user) or not unlocked(chal, user):
            abort(404)
        if is_teams_mode() and team is None:
            abort(403)

    identity = CTFdDynamicFlag.identity(df.bind or "team_name")
    if not identity:
        abort(403)

    team_id = str(team.id) if team else ""
    try:
        r = fetch(df, identity, team_id, str(user.id))
    except GeneratorError as e:
        logger.error("Dynamic file %s (%s): %s", df.id, df.endpoint, e)
        abort(502, description="This file could not be generated. Try again.")

    log(
        "submissions",
        "[{date}] {name} (team {team}) downloaded dynamic file {file} of challenge {chal}",
        name=user.name,
        team=identity,
        file=df.filename,
        chal=chal.id,
    )

    def body():
        try:
            for chunk in r.iter_content(CHUNK):
                yield chunk
        finally:
            r.close()

    headers = {"Content-Disposition": f'attachment; filename="{df.filename}"'}
    if r.headers.get("Content-Length"):
        headers["Content-Length"] = r.headers["Content-Length"]
    return Response(
        stream_with_context(body()),
        mimetype=r.headers.get("Content-Type", "application/octet-stream"),
        headers=headers,
    )
