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

Link mode: an endpoint written as link+https://host/path is a challenge web page,
not a generator. The pill then redirects the player's browser to https://host/path
with the same signed query, and the page reads the team from it.
"""

import hashlib
import hmac
import logging
import time

import requests
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, redirect, stream_with_context

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
LINK = "link+"


class GeneratorError(Exception):
    pass


def sign(secret, team, team_id, user_id, ts):
    msg = "\0".join([DOMAIN, team, team_id, user_id, ts]).encode()
    return hmac.new(bytes.fromhex(secret), msg, hashlib.sha256).hexdigest()


def signed_params(df, team, team_id, user_id):
    ts = str(int(time.time()))
    return {
        "team": team,
        "team_id": team_id,
        "user_id": user_id,
        "ts": ts,
        "sig": sign(df.secret, team, team_id, user_id, ts),
    }


def is_link(df):
    return (df.endpoint or "").startswith(LINK)


def link_url(df, team, team_id, user_id):
    """The signed URL a link-mode dynamic file sends the player to."""
    url = df.endpoint[len(LINK) :]
    sep = "&" if "?" in url else "?"
    return url + sep + urlencode(signed_params(df, team, team_id, user_id))


def fetch(df, team, team_id, user_id):
    """
    Ask the generator for team's file. Returns an open streaming response;
    the caller must close it. Raises GeneratorError on any failure.
    """
    try:
        r = requests.get(
            df.endpoint,
            params=signed_params(df, team, team_id, user_id),
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
    if is_link(df):
        log(
            "submissions",
            "[{date}] {name} (team {team}) opened dynamic link {file} of challenge {chal}",
            name=user.name,
            team=identity,
            file=df.filename,
            chal=chal.id,
        )
        return redirect(link_url(df, identity, team_id, str(user.id)), code=303)

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
