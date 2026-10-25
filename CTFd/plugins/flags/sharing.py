"""
Flag sharing detection for dynamic flags.

When a submission is wrong, check whether it is the dynamic flag of a different
team (or user, in user mode). If it is, that team's flag was shared: record a
FlagShares row and email the configured admin address.
"""

import hmac
import json
import logging
import threading
from datetime import timedelta

from flask import current_app, url_for

from CTFd.models import Fails, Flags, FlagShares, Teams, Users, db
from CTFd.plugins.flags import dynamic
from CTFd.utils import get_config
from CTFd.utils.email import sendmail
from CTFd.utils.modes import TEAMS_MODE

log = logging.getLogger(__name__)

ALERT_EMAIL_CONFIG = "flag_share_alert_email"

# India Standard Time has no daylight saving, so a fixed offset is exact
IST_OFFSET = timedelta(hours=5, minutes=30)


def format_ist(dt, suffix=True):
    """Format a naive UTC datetime from the database as IST"""
    if dt is None:
        return ""
    text = (dt + IST_OFFSET).strftime("%Y-%m-%d %H:%M:%S")
    return f"{text} IST" if suffix else text


def alert_addresses():
    raw = get_config(ALERT_EMAIL_CONFIG) or ""
    return [a.strip() for a in str(raw).split(",") if a.strip()]


def _candidates(bind):
    """
    Yield (identity, owner_user, owner_team) for every account a dynamic flag
    with this bind could belong to. Mirrors CTFdDynamicFlag.identity().
    """
    teams_mode = get_config("user_mode") == TEAMS_MODE
    if teams_mode and bind in ("team_name", "team_id"):
        for team in Teams.query.all():
            identity = team.name if bind == "team_name" else str(team.id)
            yield identity, None, team
        return

    for user in Users.query.filter_by(type="user").all():
        if bind == "user_id":
            identity = str(user.id)
        elif bind == "team_id":
            continue  # team_id needs a team; users without one never match
        else:
            identity = user.name
        yield identity, user, user.team if teams_mode else None


def find_owner(flag, provided):
    """Return (owner_user, owner_team) whose dynamic flag equals provided, or None"""
    try:
        cfg = json.loads(flag.data)
        secret = cfg["secret"]
        length = int(cfg.get("len", dynamic.DEFAULT_LENGTH))
        bind = cfg.get("bind", "team_name")
    except (ValueError, KeyError, TypeError):
        return None

    provided = provided.strip()
    for identity, owner_user, owner_team in _candidates(bind):
        expected = dynamic.make_flag(secret, identity, flag.content, length)
        if hmac.compare_digest(provided, expected):
            return owner_user, owner_team
    return None


def check_submission(user, team, challenge, provided, ip):
    """
    Called after a wrong submission is recorded. Never raises: detection must
    not break flag submission.
    """
    try:
        _check_submission(user, team, challenge, provided, ip)
    except Exception:
        db.session.rollback()
        log.exception("Flag sharing check failed for challenge %s", challenge.id)


def _check_submission(user, team, challenge, provided, ip):
    if user.type == "admin":
        return  # admins testing other teams' flags are not sharing

    flags = Flags.query.filter_by(challenge_id=challenge.id, type="dynamic").all()
    for flag in flags:
        match = find_owner(flag, provided)
        if match is None:
            continue
        owner_user, owner_team = match

        # A team's own flag is never "shared" (it would have been correct anyway)
        if team and owner_team and owner_team.id == team.id:
            continue
        if owner_user and owner_user.id == user.id:
            continue

        submission = (
            Fails.query.filter_by(user_id=user.id, challenge_id=challenge.id)
            .order_by(Fails.id.desc())
            .first()
        )
        # Same challenge, same receiving account, same flag owner
        query = FlagShares.query.filter_by(challenge_id=challenge.id)
        if team:
            query = query.filter_by(team_id=team.id)
        else:
            query = query.filter_by(user_id=user.id)
        if owner_team:
            query = query.filter_by(owner_team_id=owner_team.id)
        else:
            query = query.filter_by(owner_user_id=owner_user.id)
        first_time = query.first() is None

        share = FlagShares(
            challenge_id=challenge.id,
            flag_id=flag.id,
            submission_id=submission.id if submission else None,
            user_id=user.id,
            team_id=team.id if team else None,
            owner_user_id=owner_user.id if owner_user else None,
            owner_team_id=owner_team.id if owner_team else None,
            ip=ip,
            provided=provided.strip(),
        )
        db.session.add(share)
        db.session.commit()
        log.warning(
            "Flag sharing: %s submitted %s's flag on challenge %s",
            team.name if team else user.name,
            owner_team.name if owner_team else owner_user.name,
            challenge.id,
        )

        # One email per sharing pair per challenge, not per repeated attempt
        if first_time:
            send_alert(share)
        return


def _alert_text(share):
    shared_from = share.owner_team.name if share.owner_team else share.owner_user.name
    shared_to = share.team.name if share.team else share.user.name
    url = url_for("admin.flag_sharing_detail", share_id=share.id, _external=True)
    lines = [
        "Possible flag sharing detected.",
        "",
        f"Challenge:     {share.challenge.name} (id {share.challenge_id})",
        f"Flag owner:    {shared_from}  (the flag belongs to them)",
        f"Submitted by:  {shared_to}",
        f"Player:        {share.user.name} (user id {share.user_id})",
        f"Submitted:     {share.provided}",
        f"IP address:    {share.ip}",
        f"Time:          {format_ist(share.date)}",
        "",
        f"Details and submission log: {url}",
    ]
    return f"Flag sharing: {shared_from} -> {shared_to}", "\n".join(lines)


def send_alert(share):
    addresses = alert_addresses()
    if not addresses:
        return
    subject, text = _alert_text(share)
    subject = "[{ctf_name}] " + subject
    _send_in_background(addresses, subject, text)


def _send_in_background(addresses, subject, text):
    app = current_app._get_current_object()

    def send():
        with app.app_context():
            for address in addresses:
                ok, message = sendmail(address, text, subject=subject)
                if not ok:
                    log.error("Flag sharing alert to %s failed: %s", address, message)

    # Don't make the player's submission wait on the mail server
    if app.config.get("TESTING"):
        send()
    else:
        threading.Thread(target=send, daemon=True).start()
