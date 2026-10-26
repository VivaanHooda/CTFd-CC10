#!/usr/bin/env python
# -*- coding: utf-8 -*-

from CTFd.models import Challenges
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_challenge,
    login_as_user,
    register_user,
)


def test_challenge_subcategory_create_update_list():
    """Admins can set, change and clear a subcategory; players see it in the list"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        with login_as_user(app, "admin") as admin:
            r = admin.post(
                "/api/v1/challenges",
                json={
                    "name": "Cookie Monster",
                    "category": "Web",
                    "subcategory": "XSS",
                    "description": "d",
                    "value": 100,
                    "state": "visible",
                    "type": "standard",
                },
            )
            assert r.status_code == 200
            chal_id = r.get_json()["data"]["id"]
            assert Challenges.query.get(chal_id).subcategory == "XSS"

            # Edit page offers existing values as suggestions
            html = admin.get(f"/admin/challenges/{chal_id}").get_data(as_text=True)
            assert 'name="subcategory" value="XSS"' in html
            assert '<option value="XSS" label="Web">' in html

            r = admin.patch(
                f"/api/v1/challenges/{chal_id}", json={"subcategory": "SQLi"}
            )
            assert r.status_code == 200
            assert r.get_json()["data"]["subcategory"] == "SQLi"

            r = admin.patch(
                f"/api/v1/challenges/{chal_id}", json={"subcategory": "x" * 81}
            )
            assert r.status_code == 400

        with login_as_user(app) as client:
            r = client.get("/api/v1/challenges")
            chal = r.get_json()["data"][0]
            assert chal["category"] == "Web"
            assert chal["subcategory"] == "SQLi"

            r = client.get(f"/api/v1/challenges/{chal_id}")
            assert r.get_json()["data"]["subcategory"] == "SQLi"

        with login_as_user(app, "admin") as admin:
            r = admin.patch(f"/api/v1/challenges/{chal_id}", json={"subcategory": ""})
            assert r.status_code == 200

        with login_as_user(app) as client:
            chal = client.get("/api/v1/challenges").get_json()["data"][0]
            assert not chal["subcategory"]
    destroy_ctfd(app)


def test_challenge_without_subcategory():
    """Existing challenges without a subcategory keep working"""
    app = create_ctfd()
    with app.app_context():
        gen_challenge(app.db)
        register_user(app)
        with login_as_user(app) as client:
            chal = client.get("/api/v1/challenges").get_json()["data"][0]
            assert chal["subcategory"] is None
            assert client.get("/challenges").status_code == 200

        with login_as_user(app, "admin") as admin:
            assert admin.get("/admin/challenges").status_code == 200
            assert admin.get("/admin/challenges/new").status_code == 200
            r = admin.get("/api/v1/challenges/types")
            assert 'name="subcategory"' in r.get_json()["data"]["standard"]["create"]
    destroy_ctfd(app)
