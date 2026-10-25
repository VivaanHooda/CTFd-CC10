#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from unittest.mock import patch

from CTFd.models import FlagShares
from CTFd.plugins.flags import dynamic
from CTFd.utils import get_config, set_config
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_challenge,
    gen_flag,
    gen_team,
    login_as_user,
    register_user,
)

SECRET = "ab" * 32
BASE = "cc10{w4x}"


def setup_teams(app):
    gen_challenge(app.db, state="visible")
    gen_flag(
        app.db,
        1,
        content=BASE,
        type="dynamic",
        data=json.dumps({"secret": SECRET, "len": 10, "bind": "team_name"}),
    )
    team_a = gen_team(app.db, name="Argonauts", email="a@examplectf.com")
    team_b = gen_team(app.db, name="Trojans", email="b@examplectf.com")
    return team_a.id, team_a.members[0].name, team_b.id, team_b.members[0].name


def attempt(client, submission):
    r = client.post(
        "/api/v1/challenges/attempt",
        json={"challenge_id": 1, "submission": submission},
    )
    return r.get_json()["data"]["status"]


def test_flag_sharing_detected_and_alerted():
    """Submitting another team's dynamic flag is recorded and emails the admin once"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        a_id, _, b_id, b_user = setup_teams(app)
        set_config("flag_share_alert_email", "alerts@examplectf.com")

        with patch("CTFd.plugins.flags.sharing.sendmail") as sendmail:
            sendmail.return_value = (True, "sent")
            client_b = login_as_user(app, name=b_user)

            # A plain wrong flag is not sharing
            assert attempt(client_b, "cc10{w4x_0000000000}") == "incorrect"
            assert FlagShares.query.count() == 0

            # Team A's flag submitted by team B
            flag_a = dynamic.make_flag(SECRET, "Argonauts", BASE)
            assert attempt(client_b, flag_a) == "incorrect"
            share = FlagShares.query.one()
            assert share.owner_team_id == a_id
            assert share.team_id == b_id
            assert share.provided == flag_a
            assert share.submission_id is not None
            assert share.flag_id == 1

            sendmail.assert_called_once()
            address, text = sendmail.call_args[0][:2]
            assert address == "alerts@examplectf.com"
            assert "Argonauts" in text and "Trojans" in text and flag_a in text
            assert "IST" in text and "UTC" not in text
            assert "Argonauts -> Trojans" in sendmail.call_args[1]["subject"]

            # Repeats are recorded but don't email again
            assert attempt(client_b, flag_a) == "incorrect"
            assert FlagShares.query.count() == 2
            sendmail.assert_called_once()

            # Team B's own flag is still correct and not flagged
            assert (
                attempt(client_b, dynamic.make_flag(SECRET, "Trojans", BASE))
                == "correct"
            )
            assert FlagShares.query.count() == 2
    destroy_ctfd(app)


def test_flag_sharing_no_email_without_address():
    """Incidents are recorded even when no alert address is set"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        _, _, _, b_user = setup_teams(app)
        with patch("CTFd.plugins.flags.sharing.sendmail") as sendmail:
            client_b = login_as_user(app, name=b_user)
            attempt(client_b, dynamic.make_flag(SECRET, "Argonauts", BASE))
            assert FlagShares.query.count() == 1
            sendmail.assert_not_called()
    destroy_ctfd(app)


def test_flag_sharing_user_mode():
    """In user mode the flag owner is the other user"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db, state="visible")
        gen_flag(
            app.db, 1, content=BASE, type="dynamic", data=json.dumps({"secret": SECRET})
        )
        register_user(app, name="alice", email="alice@examplectf.com")
        register_user(app, name="bob", email="bob@examplectf.com")
        client = login_as_user(app, name="bob")
        assert attempt(client, dynamic.make_flag(SECRET, "alice", BASE)) == "incorrect"
        share = FlagShares.query.one()
        assert share.owner_user.name == "alice"
        assert share.user.name == "bob"
        assert share.team_id is None
    destroy_ctfd(app)


def test_flag_sharing_broken_flag_never_errors():
    """A misconfigured dynamic flag doesn't break submissions or record anything"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        _, _, _, b_user = setup_teams(app)
        gen_flag(app.db, 1, content="cc10{x}", type="dynamic", data="{broken")
        client_b = login_as_user(app, name=b_user)
        assert attempt(client_b, "cc10{anything}") == "incorrect"
        assert FlagShares.query.count() == 0
    destroy_ctfd(app)


def test_flag_sharing_admin_pages():
    """Admins can view incidents, set the alert email and dismiss incidents"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        _, a_user, _, b_user = setup_teams(app)
        client_b = login_as_user(app, name=b_user)
        attempt(client_b, dynamic.make_flag(SECRET, "Argonauts", BASE))
        share_id = FlagShares.query.one().id

        # Players can't see it
        client_a = login_as_user(app, name=a_user)
        assert client_a.get("/admin/flag-sharing").status_code in (302, 403)

        with login_as_user(app, "admin") as admin:
            r = admin.get("/admin/flag-sharing")
            assert r.status_code == 200
            html = r.get_data(as_text=True)
            assert "Argonauts" in html and "Trojans" in html

            r = admin.get(f"/admin/flag-sharing/{share_id}")
            assert r.status_code == 200
            html = r.get_data(as_text=True)
            assert "shared flag" in html
            assert "Submission log" in html

            with admin.session_transaction() as sess:
                nonce = sess.get("nonce")

            r = admin.post(
                "/admin/flag-sharing/settings",
                data={"alert_email": "not-an-email", "nonce": nonce},
            )
            assert "notice=bad_email" in r.headers["Location"]
            r = admin.post(
                "/admin/flag-sharing/settings",
                data={"alert_email": "a@x.com, b@x.com", "nonce": nonce},
            )
            assert "notice=saved" in r.headers["Location"]
            assert get_config("flag_share_alert_email") == "a@x.com, b@x.com"

            # No mail server configured: the test email explains that
            r = admin.post("/admin/flag-sharing/test-email", data={"nonce": nonce})
            assert "notice=no_mail_server" in r.headers["Location"]

            r = admin.post(
                f"/admin/flag-sharing/{share_id}/dismiss", data={"nonce": nonce}
            )
            assert r.status_code == 302
            assert FlagShares.query.count() == 0
    destroy_ctfd(app)


def test_flag_sharing_times_in_ist():
    """Times are shown in IST (UTC+5:30)"""
    from datetime import datetime

    from CTFd.plugins.flags.sharing import format_ist

    assert format_ist(datetime(2026, 10, 25, 20, 0, 0)) == "2026-10-26 01:30:00 IST"
    assert format_ist(datetime(2026, 10, 25, 20, 0, 0), suffix=False) == (
        "2026-10-26 01:30:00"
    )
