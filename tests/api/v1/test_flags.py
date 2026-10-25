#!/usr/bin/env python
# -*- coding: utf-8 -*-

from CTFd.models import Flags
from CTFd.utils import set_config
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_challenge,
    gen_flag,
    login_as_user,
    register_user,
)


def test_api_flags_get_non_admin():
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_flag(app.db, 1)

        with app.test_client() as client:
            # test_api_flags_get_non_admin
            """Can a user get /api/v1/flags if not admin"""
            r = client.get("/api/v1/flags", json="")
            assert r.status_code == 403

            # test_api_flags_post_non_admin
            """Can a user post /api/v1/flags if not admin"""
            r = client.post("/api/v1/flags")
            assert r.status_code == 403

            # test_api_flag_types_get_non_admin
            """Can a user get /api/v1/flags/types[/<type_name>] if not admin"""
            r = client.get("/api/v1/flags/types", json="")
            assert r.status_code == 403

            # test_api_flag_get_non_admin
            """Can a user get /api/v1/flags/<flag_id> if not admin"""
            r = client.get("/api/v1/flags/1", json="")
            assert r.status_code == 403

            # test_api_flag_patch_non_admin
            """Can a user patch /api/v1/flags/<flag_id> if not admin"""
            r = client.patch("/api/v1/flags/1", json="")
            assert r.status_code == 403

            # test_api_flag_delete_non_admin
            """Can a user delete /api/v1/flags/<flag_id> if not admin"""
            r = client.delete("/api/v1/flags/1", json="")
            assert r.status_code == 403
    destroy_ctfd(app)


def test_api_flags_get_admin():
    """Can a user get /api/v1/flags if admin"""
    app = create_ctfd()
    with app.app_context():
        with login_as_user(app, "admin") as client:
            r = client.get("/api/v1/flags", json="")
            assert r.status_code == 200
    destroy_ctfd(app)


def test_api_flags_post_admin():
    """Can a user post /api/v1/flags if admin"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        with login_as_user(app, name="admin") as client:
            r = client.post(
                "/api/v1/flags",
                json={"content": "flag", "type": "static", "challenge": 1},
            )
            assert r.status_code == 200
    destroy_ctfd(app)


def test_api_flag_types_get_admin():
    """Can a user get /api/v1/flags/types[/<type_name>] if admin"""
    app = create_ctfd()
    with app.app_context():
        with login_as_user(app, "admin") as client:
            r = client.get("/api/v1/flags/types", json="")
            assert r.status_code == 200
            r = client.get("/api/v1/flags/types/static", json="")
            assert r.status_code == 200
    destroy_ctfd(app)


def test_api_flag_get_admin():
    """Can a user get /api/v1/flags/<flag_id> if admin"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_flag(app.db, 1)
        with login_as_user(app, "admin") as client:
            r = client.get("/api/v1/flags/1", json="")
            assert r.status_code == 200
    destroy_ctfd(app)


def test_api_flag_patch_admin():
    """Can a user patch /api/v1/flags/<flag_id> if admin"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_flag(app.db, 1)
        with login_as_user(app, "admin") as client:
            r = client.patch(
                "/api/v1/flags/1",
                json={"content": "flag_edit", "data": "", "type": "static", "id": "1"},
            )
            assert r.status_code == 200
            assert r.get_json()["data"]["content"] == "flag_edit"
    destroy_ctfd(app)


def test_api_flag_delete_admin():
    """Can a user patch /api/v1/flags/<flag_id> if admin"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        gen_flag(app.db, 1)
        with login_as_user(app, "admin") as client:
            r = client.delete("/api/v1/flags/1", json="")
            assert r.status_code == 200
            assert r.get_json().get("data") is None
    destroy_ctfd(app)


def test_flag_content_stripped_on_create_and_update():
    """Test that flag content is stripped of whitespace on create and update"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        with login_as_user(app, "admin") as client:
            # Create flag with whitespace
            r = client.post(
                "/api/v1/flags",
                json={
                    "content": "   flag_with_spaces   ",
                    "type": "static",
                    "challenge": 1,
                },
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "flag_with_spaces"

            flag_id = data["id"]

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "flag_with_spaces"

            # Update flag with whitespace
            r = client.patch(
                f"/api/v1/flags/{flag_id}",
                json={"content": "   updated_flag   ", "type": "static"},
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "updated_flag"

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "updated_flag"
    destroy_ctfd(app)


def test_flag_content_stripped_on_create_and_update_regex():
    """Test that regex flag content is stripped of whitespace on create and update"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        with login_as_user(app, "admin") as client:
            # Create regex flag with whitespace
            r = client.post(
                "/api/v1/flags",
                json={
                    "content": "   ^flag\\d+$   ",
                    "type": "regex",
                    "challenge": 1,
                },
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "^flag\\d+$"

            flag_id = data["id"]

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "^flag\\d+$"

            # Update regex flag with whitespace
            r = client.patch(
                f"/api/v1/flags/{flag_id}",
                json={"content": "   ^updated_flag\\d+$   ", "type": "regex"},
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "^updated_flag\\d+$"

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "^updated_flag\\d+$"


def test_flag_content_not_stripped_on_other_types():
    """Test that flag content is not stripped for non-static and non-regex types"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        with login_as_user(app, "admin") as client:
            # Create flag with a custom type
            r = client.post(
                "/api/v1/flags",
                json={
                    "content": "   custom_flag   ",
                    "type": "custom",
                    "challenge": 1,
                },
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            # Should not be stripped
            assert data["content"] == "   custom_flag   "

            flag_id = data["id"]

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "   custom_flag   "

            # Update flag with whitespace
            r = client.patch(
                f"/api/v1/flags/{flag_id}",
                json={"content": "   updated_custom_flag   ", "type": "custom"},
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "   updated_custom_flag   "

            f = Flags.query.filter_by(id=flag_id).first()
            assert f.content == "   updated_custom_flag   "


def test_api_dynamic_flags():
    """Dynamic flags: key generation, own key, key edits, preview, per-team checks"""
    import json

    from CTFd.models import Challenges
    from CTFd.plugins.flags import dynamic
    from tests.helpers import gen_team

    secret = "ab" * 32
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        gen_challenge(app.db, state="visible")
        team_a = gen_team(app.db, name="Argonauts", email="a@examplectf.com")
        team_b = gen_team(app.db, name="Trojans", email="b@examplectf.com")
        user_a = team_a.members[0].name
        user_b = team_b.members[0].name
        assert Challenges.query.count() == 1

        with login_as_user(app, "admin") as admin:
            # No key given: the server generates one
            r = admin.post(
                "/api/v1/flags",
                json={"challenge": 1, "type": "dynamic", "content": " cc10{gen} "},
            )
            assert r.status_code == 200
            data = r.get_json()["data"]
            assert data["content"] == "cc10{gen}"
            assert len(json.loads(data["data"])["secret"]) == 64

            # Admin's own key is stored as typed
            r = admin.post(
                "/api/v1/flags",
                json={
                    "challenge": 1,
                    "type": "dynamic",
                    "content": "cc10{own}",
                    "data": json.dumps({"secret": secret}),
                },
            )
            own_id = r.get_json()["data"]["id"]
            assert json.loads(Flags.query.get(own_id).data)["secret"] == secret

            # Bad key is rejected
            r = admin.post(
                "/api/v1/flags",
                json={
                    "challenge": 1,
                    "type": "dynamic",
                    "content": "cc10{x}",
                    "data": json.dumps({"secret": "zz"}),
                },
            )
            assert r.status_code == 400

            # Editing only the text keeps the key; sending a new key changes it
            r = admin.patch(f"/api/v1/flags/{own_id}", json={"content": "cc10{w4x}"})
            assert r.status_code == 200
            assert json.loads(Flags.query.get(own_id).data)["secret"] == secret
            r = admin.patch(
                f"/api/v1/flags/{own_id}",
                json={"data": json.dumps({"secret": "cd" * 32})},
            )
            assert r.status_code == 200
            assert json.loads(Flags.query.get(own_id).data)["secret"] == "cd" * 32
            admin.patch(
                f"/api/v1/flags/{own_id}", json={"data": json.dumps({"secret": secret})}
            )

            # Preview shows each team's flag
            r = admin.get(f"/api/v1/flags/{own_id}/preview?identity=Argonauts")
            flag_a = r.get_json()["data"]["flag"]
            assert flag_a == dynamic.make_flag(secret, "Argonauts", "cc10{w4x}")
            r = admin.get(f"/api/v1/flags/{own_id}/preview?identity=Trojans")
            flag_b = r.get_json()["data"]["flag"]

            # AI-agent prompt is built from form values and includes team A's flag
            r = admin.post(
                "/api/v1/flags/agent-prompt",
                json={"content": "cc10{w4x}", "data": {"secret": secret}},
            )
            assert r.status_code == 200
            assert secret in r.get_json()["data"]["prompt"]
            # Warns while teams can still rename themselves
            assert r.get_json()["data"]["warnings"]
            set_config("name_changes", False)
            r = admin.post(
                "/api/v1/flags/agent-prompt",
                json={"content": "cc10{w4x}", "data": {"secret": secret}},
            )
            assert r.get_json()["data"]["warnings"] == []

        # Preview and prompt are admin only
        with app.test_client() as client:
            r = client.get(f"/api/v1/flags/{own_id}/preview?identity=Argonauts")
            assert r.status_code in (302, 403)
            r = client.post("/api/v1/flags/agent-prompt", json={"content": "x"})
            assert r.status_code in (302, 403)

        # Team B can't use team A's flag; each team's own flag works
        client_b = login_as_user(app, name=user_b)
        r = client_b.post(
            "/api/v1/challenges/attempt",
            json={"challenge_id": 1, "submission": flag_a},
        )
        assert r.get_json()["data"]["status"] == "incorrect"
        r = client_b.post(
            "/api/v1/challenges/attempt",
            json={"challenge_id": 1, "submission": flag_b},
        )
        assert r.get_json()["data"]["status"] == "correct"

        client_a = login_as_user(app, name=user_a)
        r = client_a.post(
            "/api/v1/challenges/attempt",
            json={"challenge_id": 1, "submission": flag_a},
        )
        assert r.get_json()["data"]["status"] == "correct"
    destroy_ctfd(app)


def test_api_dynamic_flag_bad_data_rejects():
    """A misconfigured dynamic flag rejects submissions instead of erroring"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db, state="visible")
        gen_flag(app.db, 1, content="cc10{x}", type="dynamic", data="{broken")
        register_user(app)
        with login_as_user(app) as client:
            r = client.post(
                "/api/v1/challenges/attempt",
                json={"challenge_id": 1, "submission": "cc10{x}"},
            )
            assert r.status_code == 200
            assert r.get_json()["data"]["status"] == "incorrect"
    destroy_ctfd(app)
