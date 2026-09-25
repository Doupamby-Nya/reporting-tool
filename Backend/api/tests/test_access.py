"""Who reaches which module, and whose data they see.

A module's tab being hidden in the browser protects nothing; these tests
prove the API itself refuses — for every one of the eight modules.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from _auth import PASSWORD, ensure_org, login_as
from database.tables import Role
from main import app
from services.authService import MODULE_KEYS

# One read-only route per module, cheap and free of side effects.
PROBES = {
    "priips": "/api/v1/priips/parameters",
    "fatca": "/api/v1/fatca/filer-categories",
    "urr": "/api/v1/urr/form",
    "o41": "/api/v1/o41/form",
    "esef": "/api/v1/esef/form",
    "aifmd": "/api/v1/aifmd/metadata",
    "saq": "/api/v1/saq/form",
    "bcl": "/api/v1/bcl/reports",
}

YESTERDAY = date.today() - timedelta(days=1)


def test_every_module_has_a_probe():
    assert set(PROBES) == set(MODULE_KEYS)


@pytest.mark.parametrize("module", MODULE_KEYS)
def test_anonymous_visitors_are_asked_to_sign_in(module):
    response = TestClient(app).get(PROBES[module])
    assert response.status_code == 401
    assert response.json() == {"success": False, "message": "Sign in to continue."}


def test_the_module_catalogue_is_public():
    """The home page presents the modules to visitors."""
    response = TestClient(app).get("/api/v1/reference/modules")
    assert response.status_code == 200
    assert {m["key"] for m in response.json()["result"]} == set(MODULE_KEYS)


@pytest.mark.parametrize("module", MODULE_KEYS)
def test_a_user_reaches_only_the_module_their_organisation_pays_for(module):
    org = ensure_org(f"Only {module}", modules=(module,))
    client = login_as(f"only-{module}@client.lu", org, modules=(module,))
    for other, probe in PROBES.items():
        expected = 200 if other == module else 403
        assert client.get(probe).status_code == expected, (other, probe)


@pytest.mark.parametrize("module", MODULE_KEYS)
def test_an_expired_subscription_closes_the_module(module):
    org = ensure_org(f"Expired {module}", modules=(module,), valid_until=YESTERDAY)
    client = login_as(f"expired-{module}@client.lu", org, modules=(module,))
    assert client.get(PROBES[module]).status_code == 403
    assert client.get("/api/v1/auth/me").json()["result"]["modules"] == []


def test_a_subscription_opens_a_module_only_to_the_users_assigned_to_it():
    org = ensure_org("Two modules", modules=("bcl", "urr"))
    client = login_as("bcl-only@client.lu", org, modules=("bcl",))
    assert client.get(PROBES["bcl"]).status_code == 200
    assert client.get(PROBES["urr"]).status_code == 403


def test_an_organisation_admin_uses_every_module_the_organisation_pays_for():
    org = ensure_org("Admin's organisation", modules=("bcl", "urr"))
    client = login_as("org-admin@client.lu", org, role=Role.org_admin, modules=())
    assert client.get(PROBES["bcl"]).status_code == 200
    assert client.get(PROBES["urr"]).status_code == 200
    assert client.get(PROBES["saq"]).status_code == 403


def test_me_lists_the_usable_modules_with_their_end_date():
    until = date.today() + timedelta(days=30)
    org = ensure_org("Dated", modules=("saq",), valid_until=until)
    me = login_as("dated@client.lu", org, modules=("saq",)).get("/api/v1/auth/me").json()["result"]
    assert me["organisation"] == "Dated"
    assert me["modules"] == [{"key": "saq", "valid_until": until.isoformat()}]


def test_routes_naming_a_module_are_guarded_too():
    """Drafts, documents and the regulatory library are shared routes that
    carry the module in their path."""
    org = ensure_org("Guarded", modules=("bcl",))
    client = login_as("guarded@client.lu", org, modules=("bcl",))
    assert client.get("/api/v1/drafts/bcl").status_code == 200
    for path in ("/api/v1/drafts/urr", "/api/v1/documents/urr", "/api/v1/reference/regulations/urr"):
        assert client.get(path).status_code == 403, path


def test_organisations_do_not_see_each_other_s_data():
    a = login_as("alice@org-a.lu", ensure_org("Org A", modules=("bcl", "priips")), modules=("bcl", "priips"))
    b = login_as("bob@org-b.lu", ensure_org("Org B", modules=("bcl", "priips")), modules=("bcl", "priips"))

    assert a.post("/api/v1/drafts/bcl", json={"name": "A's draft", "data": {"x": 1}}).status_code == 200
    assert a.post("/api/v1/funds/demo").status_code == 200

    assert [d["name"] for d in b.get("/api/v1/drafts/bcl").json()["result"]] == []
    assert b.get("/api/v1/drafts/bcl/A's draft").status_code == 404
    assert b.get("/api/v1/funds").json()["result"] == []
    assert a.get("/api/v1/funds").json()["result"] != []


def test_the_audit_trail_shows_only_the_reader_s_modules():
    org = ensure_org("Audit split", modules=("bcl", "urr"))
    both = login_as("both@audit.lu", org, modules=("bcl", "urr"))
    bcl_only = login_as("bcl@audit.lu", org, modules=("bcl",))
    both.post("/api/v1/documents/urr", json={"document_id": "U.xml", "label": "U 1.1"})
    both.post("/api/v1/documents/bcl", json={"document_id": "B.xml", "label": "S 1.3"})

    seen = {e["subject"] for e in bcl_only.get("/api/v1/audit").json()["result"]}
    assert "B.xml" in seen and "U.xml" not in seen


def test_deleting_a_draft_is_logged_against_the_user():
    org = ensure_org("Deleter", modules=("bcl",))
    client = login_as("deleter@client.lu", org, modules=("bcl",))
    client.post("/api/v1/drafts/bcl", json={"name": "Gone", "data": {}})
    assert client.delete("/api/v1/drafts/bcl/Gone").status_code == 200
    entry = client.get("/api/v1/audit").json()["result"][0]
    assert (entry["action"], entry["subject"], entry["user"]) == ("BCL draft deleted", "Gone", "deleter@client.lu")


def test_a_wrong_password_is_refused_without_saying_which_part_was_wrong():
    login_as("known@client.lu")
    client = TestClient(app)
    wrong = client.post("/api/v1/auth/login", json={"email": "known@client.lu", "password": "not it at all"})
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@client.lu", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"]


def test_signing_out_ends_the_session():
    client = login_as("leaver@client.lu")
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_shared_priips_configuration_is_for_platform_admins():
    # An organisation of its own: the settings it saves must not reach the
    # organisation the non-regression cases run in.
    org = ensure_org("PRIIPs settings", modules=("priips",))
    user = login_as("priips-user@client.lu", org, modules=("priips",))
    assert user.put("/api/v1/priips/parameters", json={}).status_code == 403
    assert user.put("/api/v1/priips/settings", json={"organisation_name": "Mine"}).status_code == 200


def test_the_platform_admin_opens_a_module_and_the_user_gets_it():
    admin = login_as("platform@admin.lu", role=Role.platform_admin, modules=())
    assert login_as("not-admin@client.lu").get("/api/v1/admin/users").status_code == 403

    org = admin.post("/api/v1/admin/organisations", json={"name": "New client", "kind": "external"}).json()["result"]
    user = admin.post("/api/v1/admin/users", json={
        "organisation_id": org["id"], "email": "new@client.lu", "name": "New",
        "password": PASSWORD, "modules": ["esef"]}).json()["result"]

    client = TestClient(app)
    client.post("/api/v1/auth/login", json={"email": "new@client.lu", "password": PASSWORD})
    assert client.get(PROBES["esef"]).status_code == 403       # not paid yet

    assert admin.post("/api/v1/admin/subscriptions", json={
        "organisation_id": org["id"], "module": "esef",
        "valid_from": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=365)).isoformat()}).status_code == 200
    assert client.get(PROBES["esef"]).status_code == 200      # paid

    assert admin.put(f"/api/v1/admin/users/{user['id']}/active", json={"active": False}).status_code == 200
    assert client.get(PROBES["esef"]).status_code == 401      # disabled: the session is gone
