#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import patch

import requests

from CTFd.dynamic_files import sign
from CTFd.models import DynamicFiles
from CTFd.utils import set_config
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_challenge,
    gen_team,
    login_as_user,
    register_user,
)

SECRET = "cd" * 32
GET = "CTFd.dynamic_files.requests.get"


class FakeResponse:
    def __init__(self, body=b"per-team bytes", status_code=200):
        self.body = body
        self.status_code = status_code
        self.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(body)),
        }
        self.closed = False

    def iter_content(self, size):
        yield self.body

    def close(self):
        self.closed = True


def gen_dynamic_file(db, challenge_id=1, **kwargs):
    df = DynamicFiles(
        challenge_id=challenge_id,
        filename=kwargs.get("filename", "fleet.jpg"),
        endpoint=kwargs.get("endpoint", "http://127.0.0.1:10130/ctfd"),
        secret=kwargs.get("secret", SECRET),
        bind=kwargs.get("bind", "team_name"),
        timeout=kwargs.get("timeout", 60),
    )
    db.session.add(df)
    db.session.commit()
    return df


def test_dynamic_file_api_non_admin():
    """Players cannot list, create, edit, delete or test dynamic files"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        register_user(app)
        with login_as_user(app) as client:
            assert client.get("/api/v1/dynamic_files", json="").status_code == 403
            assert client.post("/api/v1/dynamic_files", json={}).status_code == 403
            assert client.get("/api/v1/dynamic_files/1", json="").status_code == 403
            assert client.patch("/api/v1/dynamic_files/1", json={}).status_code == 403
            assert client.delete("/api/v1/dynamic_files/1", json="").status_code == 403
            r = client.get("/api/v1/dynamic_files/1/test?team=x", json="")
            assert r.status_code == 403
    destroy_ctfd(app)


def test_dynamic_file_api_admin_crud():
    """Admins can create, edit and delete dynamic files; bad input is rejected"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        with login_as_user(app, "admin") as admin:
            r = admin.post(
                "/api/v1/dynamic_files",
                json={
                    "challenge_id": 1,
                    "filename": "fleet.jpg",
                    "endpoint": "http://127.0.0.1:10130/ctfd",
                },
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert len(data["secret"]) == 64
            assert data["bind"] == "team_name"

            for bad in (
                {"filename": "../x"},
                {"endpoint": "file:///etc/passwd"},
                {"secret": "zz"},
                {"bind": "email"},
                {"timeout": 0},
            ):
                r = admin.patch(f"/api/v1/dynamic_files/{data['id']}", json=bad)
                assert r.status_code == 400, bad

            r = admin.post("/api/v1/dynamic_files", json={"challenge_id": 1})
            assert r.status_code == 400

            r = admin.patch(
                f"/api/v1/dynamic_files/{data['id']}",
                json={"filename": "fleet2.jpg", "secret": SECRET},
            )
            assert r.status_code == 200
            df = DynamicFiles.query.get(data["id"])
            assert df.filename == "fleet2.jpg"
            assert df.secret == SECRET

            r = admin.get("/api/v1/dynamic_files?challenge_id=1", json="")
            assert len(r.get_json()["data"]) == 1

            r = admin.delete(f"/api/v1/dynamic_files/{data['id']}", json="")
            assert r.status_code == 200
            assert DynamicFiles.query.count() == 0
    destroy_ctfd(app)


def test_dynamic_file_listed_with_challenge_files():
    """The challenge API lists a dynamic file like any other file"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        register_user(app)
        with login_as_user(app) as client:
            files = client.get("/api/v1/challenges/1").get_json()["data"]["files"]
            assert files == ["/files/dynamic/1/fleet.jpg"]
    destroy_ctfd(app)


def test_dynamic_file_download_signed_per_team():
    """Each team gets its own file, fetched with a valid signature over its name"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        team_a = gen_team(app.db, name="Argonauts", email="a@examplectf.com")
        team_b = gen_team(app.db, name="Trojans", email="b@examplectf.com")
        user_a = team_a.members[0]
        user_b = team_b.members[0]
        user_a_name, user_a_id, team_a_id = user_a.name, user_a.id, team_a.id
        user_b_name = user_b.name

        with patch(GET, return_value=FakeResponse()) as get:
            with login_as_user(app, user_a_name) as client:
                r = client.get("/files/dynamic/1/fleet.jpg")
                assert r.status_code == 200
                assert r.data == b"per-team bytes"
                assert r.headers["Content-Type"] == "image/jpeg"
                assert 'filename="fleet.jpg"' in r.headers["Content-Disposition"]

            url = get.call_args.args[0]
            params = get.call_args.kwargs["params"]
            assert url == "http://127.0.0.1:10130/ctfd"
            assert params["team"] == "Argonauts"
            assert params["team_id"] == str(team_a_id)
            assert params["user_id"] == str(user_a_id)
            assert params["sig"] == sign(
                SECRET, "Argonauts", str(team_a_id), str(user_a_id), params["ts"]
            )

            with login_as_user(app, user_b_name) as client:
                assert client.get("/files/dynamic/1/fleet.jpg").status_code == 200
            assert get.call_args.kwargs["params"]["team"] == "Trojans"
    destroy_ctfd(app)


def test_dynamic_file_download_access_rules():
    """Logged out, teamless, hidden and outside CTF time are all refused"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        team = gen_team(app.db, name="Argonauts", email="a@examplectf.com")
        member = team.members[0].name
        register_user(app, name="loner", email="loner@examplectf.com")

        with patch(GET, return_value=FakeResponse()) as get:
            with app.test_client() as anon:
                r = anon.get("/files/dynamic/1/fleet.jpg")
                assert r.status_code == 302
                assert "/login" in r.location

            with login_as_user(app, "loner") as client:
                r = client.get("/files/dynamic/1/fleet.jpg")
                assert r.status_code in (302, 403)

            with login_as_user(app, member) as client:
                assert client.get("/files/dynamic/9/fleet.jpg").status_code == 404

                set_config("end", "1507262400")  # 2017, long over
                assert client.get("/files/dynamic/1/fleet.jpg").status_code == 403
                set_config("end", None)

                chal = DynamicFiles.query.get(1).challenge
                chal.state = "hidden"
                app.db.session.commit()
                assert client.get("/files/dynamic/1/fleet.jpg").status_code == 404

            get.assert_not_called()
    destroy_ctfd(app)


def test_dynamic_file_generator_failure_is_502():
    """A dead or failing generator gives a clean 502, never a 500"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        register_user(app)
        with login_as_user(app) as client:
            with patch(GET, side_effect=requests.ConnectionError("refused")):
                assert client.get("/files/dynamic/1/fleet.jpg").status_code == 502
            bad = FakeResponse(status_code=403)
            with patch(GET, return_value=bad):
                assert client.get("/files/dynamic/1/fleet.jpg").status_code == 502
            assert bad.closed
    destroy_ctfd(app)


def test_dynamic_file_admin_test_endpoint():
    """The admin Test button fetches once as the named team"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        with login_as_user(app, "admin") as admin:
            with patch(GET, return_value=FakeResponse(b"x" * 10)) as get:
                r = admin.get("/api/v1/dynamic_files/1/test?team=Argonauts", json="")
                assert r.status_code == 200
                assert r.get_json()["data"]["bytes"] == 10
                assert get.call_args.kwargs["params"]["team"] == "Argonauts"
            with patch(GET, side_effect=requests.Timeout("slow")):
                r = admin.get("/api/v1/dynamic_files/1/test?team=Argonauts", json="")
                assert r.status_code == 502
    destroy_ctfd(app)


def test_dynamic_files_deleted_with_challenge():
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_dynamic_file(app.db)
        with login_as_user(app, "admin") as admin:
            assert admin.delete("/api/v1/challenges/1", json="").status_code == 200
        assert DynamicFiles.query.count() == 0
    destroy_ctfd(app)
