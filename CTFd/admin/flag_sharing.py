from flask import redirect, render_template, request, url_for
from sqlalchemy import func, or_

from CTFd.admin import admin
from CTFd.models import FlagShares, Solves, Submissions, db
from CTFd.plugins.flags import sharing
from CTFd.utils import get_config, set_config, validators
from CTFd.utils.config import can_send_mail
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail
from CTFd.utils.modes import TEAMS_MODE

NOTICES = {
    "saved": ("success", "Alert email saved."),
    "cleared": ("success", "Alert email removed. No alerts will be sent."),
    "test_sent": ("success", "Test email sent. Check the inbox (and spam folder)."),
    "dismissed": ("success", "Incident dismissed."),
    "bad_email": ("danger", "That doesn't look like a valid email address."),
    "no_email": ("danger", "Save an alert email address first."),
    "no_mail_server": (
        "danger",
        "No mail server is set up. Configure it in Config > Email.",
    ),
}


@admin.app_template_filter("ist")
def ist_filter(dt, suffix=False):
    return sharing.format_ist(dt, suffix=suffix)


def _notice():
    key = request.args.get("notice")
    if key == "test_failed":
        return ("danger", "Test email failed. " + request.args.get("detail", ""))
    return NOTICES.get(key)


def _account_filter(model, team_id, user_id):
    # Teams mode records both; match on team so all members' activity shows
    if team_id:
        return model.team_id == team_id
    return model.user_id == user_id


@admin.route("/admin/flag-sharing")
@admins_only
def flag_sharing_listing():
    page = abs(request.args.get("page", 1, type=int))
    shares = FlagShares.query.order_by(
        FlagShares.date.desc(), FlagShares.id.desc()
    ).paginate(page=page, per_page=50, error_out=False)

    # Who shared with whom, across all challenges
    receiver = (
        FlagShares.team_id
        if get_config("user_mode") == TEAMS_MODE
        else FlagShares.user_id
    )
    pairs = (
        db.session.query(
            FlagShares.owner_team_id,
            FlagShares.owner_user_id,
            receiver,
            func.count(FlagShares.id).label("count"),
            func.count(func.distinct(FlagShares.challenge_id)).label("challenges"),
            func.max(FlagShares.date).label("last"),
            func.max(FlagShares.id).label("latest_id"),
        )
        .group_by(FlagShares.owner_team_id, FlagShares.owner_user_id, receiver)
        .order_by(func.max(FlagShares.date).desc())
        .all()
    )
    latest = {
        s.id: s
        for s in FlagShares.query.filter(
            FlagShares.id.in_([p.latest_id for p in pairs])
        ).all()
    }

    return render_template(
        "admin/flag_sharing/listing.html",
        shares=shares,
        pairs=[(p, latest[p.latest_id]) for p in pairs if p.latest_id in latest],
        alert_email=get_config(sharing.ALERT_EMAIL_CONFIG) or "",
        mail_ready=can_send_mail(),
        notice=_notice(),
        prev_page=url_for(request.endpoint, page=shares.prev_num),
        next_page=url_for(request.endpoint, page=shares.next_num),
    )


@admin.route("/admin/flag-sharing/<int:share_id>")
@admins_only
def flag_sharing_detail(share_id):
    share = FlagShares.query.filter_by(id=share_id).first_or_404()

    receiver = _account_filter(Submissions, share.team_id, share.user_id)
    owner = _account_filter(Submissions, share.owner_team_id, share.owner_user_id)
    log = (
        Submissions.query.filter(
            Submissions.challenge_id == share.challenge_id, or_(receiver, owner)
        )
        .order_by(Submissions.date.asc(), Submissions.id.asc())
        .all()
    )

    owner_solve = Solves.query.filter(
        Solves.challenge_id == share.challenge_id,
        _account_filter(Solves, share.owner_team_id, share.owner_user_id),
    ).first()
    receiver_solve = Solves.query.filter(
        Solves.challenge_id == share.challenge_id,
        _account_filter(Solves, share.team_id, share.user_id),
    ).first()

    # Every incident between these two accounts, on any challenge
    related = (
        FlagShares.query.filter(
            _account_filter(FlagShares, share.team_id, share.user_id),
            FlagShares.owner_team_id == share.owner_team_id
            if share.owner_team_id
            else FlagShares.owner_user_id == share.owner_user_id,
        )
        .order_by(FlagShares.date.desc())
        .all()
    )
    shared_submission_ids = {
        s.submission_id
        for s in FlagShares.query.filter_by(challenge_id=share.challenge_id).all()
    }

    return render_template(
        "admin/flag_sharing/detail.html",
        share=share,
        log=log,
        owner_solve=owner_solve,
        receiver_solve=receiver_solve,
        related=related,
        shared_submission_ids=shared_submission_ids,
        notice=_notice(),
    )


@admin.route("/admin/flag-sharing/settings", methods=["POST"])
@admins_only
def flag_sharing_settings():
    raw = request.form.get("alert_email", "")
    addresses = [a.strip() for a in raw.split(",") if a.strip()]
    if not addresses:
        set_config(sharing.ALERT_EMAIL_CONFIG, "")
        return redirect(url_for("admin.flag_sharing_listing", notice="cleared"))
    if not all(validators.validate_email(a) for a in addresses):
        return redirect(url_for("admin.flag_sharing_listing", notice="bad_email"))
    set_config(sharing.ALERT_EMAIL_CONFIG, ", ".join(addresses))
    return redirect(url_for("admin.flag_sharing_listing", notice="saved"))


@admin.route("/admin/flag-sharing/test-email", methods=["POST"])
@admins_only
def flag_sharing_test_email():
    addresses = sharing.alert_addresses()
    if not addresses:
        return redirect(url_for("admin.flag_sharing_listing", notice="no_email"))
    if not can_send_mail():
        return redirect(url_for("admin.flag_sharing_listing", notice="no_mail_server"))

    text = (
        "This is a test of the flag sharing alert.\n\n"
        "When one team submits another team's dynamic flag, an email like this "
        "is sent with the details.\n\n"
        f"Flag sharing page: {url_for('admin.flag_sharing_listing', _external=True)}"
    )
    for address in addresses:
        ok, message = sendmail(
            address, text, subject="[{ctf_name}] Flag sharing alert test"
        )
        if not ok:
            return redirect(
                url_for(
                    "admin.flag_sharing_listing",
                    notice="test_failed",
                    detail=f"{address}: {message}",
                )
            )
    return redirect(url_for("admin.flag_sharing_listing", notice="test_sent"))


@admin.route("/admin/flag-sharing/<int:share_id>/dismiss", methods=["POST"])
@admins_only
def flag_sharing_dismiss(share_id):
    share = FlagShares.query.filter_by(id=share_id).first_or_404()
    db.session.delete(share)
    db.session.commit()
    return redirect(url_for("admin.flag_sharing_listing", notice="dismissed"))
