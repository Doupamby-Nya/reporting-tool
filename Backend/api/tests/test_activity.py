"""The activity record and the usage dashboards drawn from it.

What counts as work is recorded, what only draws a screen is not, a refused
request leaves no trace, and nobody sees activity outside their reach: a
user sees themselves, an organisation administrator their organisation, a
platform administrator any.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from _auth import ensure_org, login_as
from database.tables import Role
from services import activityService


def result(response):
    payload = response.json()
    assert payload["success"], payload
    return payload["result"]


# =============================================================================
# Classification
# =============================================================================

@pytest.mark.parametrize(("method", "path", "query", "expected"), [
    ("POST", "/api/v1/documents/bcl", {}, ("bcl", "generated", None)),
    ("POST", "/api/v1/documents/esef/PKG.zip/status", {}, ("esef", "reviewed", "PKG.zip")),
    ("POST", "/api/v1/bcl/s13/validate", {}, ("bcl", "validated", "s13")),
    ("POST", "/api/v1/aifmd/validate", {}, ("aifmd", "validated", None)),
    ("POST", "/api/v1/urr/parse", {}, ("urr", "ingested", None)),
    ("POST", "/api/v1/aifmd/template/parse", {}, ("aifmd", "ingested", None)),
    ("POST", "/api/v1/fatca/inspect", {}, ("fatca", "ingested", None)),
    ("POST", "/api/v1/drafts/o41", {}, ("o41", "drafted", None)),
    ("DELETE", "/api/v1/drafts/o41/march", {}, ("o41", "deleted", "march")),
    ("GET", "/api/v1/reference/regulations/urr/0/download", {}, ("urr", "consulted", None)),
    ("GET", "/api/v1/reference/regulations/chain/1/download", {}, ("priips", "consulted", None)),
    ("GET", "/api/v1/reference/regulations/urr/0/download", {"download": "true"}, ("urr", "downloaded", None)),
    ("GET", "/api/v1/bcl/s13/reference/rules", {"inline": "true"}, ("bcl", "consulted", "s13")),
    ("GET", "/api/v1/bcl/s13/reference/report", {}, ("bcl", "downloaded", "s13")),
    ("GET", "/api/v1/bcl/s13/reference/report/preview", {}, ("bcl", "consulted", "s13")),
    ("GET", "/api/v1/fatca/template", {}, ("fatca", "downloaded", None)),
    ("PUT", "/api/v1/priips/settings", {}, ("priips", "configured", None)),
    ("POST", "/api/v1/auth/login", {}, ("platform", "signed_in", None)),
    ("PUT", "/api/v1/admin/users/3/modules", {}, ("platform", "administered", None)),
])
def test_work_is_classified(method, path, query, expected):
    assert activityService.classify(method, path, query) == expected


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/v1/urr/form"),            # drawing a form is not work
    ("GET", "/api/v1/bcl/reports"),
    ("GET", "/api/v1/drafts/bcl"),
    ("POST", "/api/v1/urr/rules"),          # the catalogue, read on every visit
    ("POST", "/api/v1/urr/generate"),       # counted once, when the filing is registered
    ("GET", "/api/v1/auth/me"),
    ("GET", "/healthcheck"),
])
def test_screens_are_not_work(method, path):
    assert activityService.classify(method, path, {}) is None


def test_streaks_count_consecutive_days_and_forgive_an_unfinished_today():
    today = date(2026, 9, 25)
    days = {today - timedelta(days=n) for n in (1, 2, 3, 7, 8)}
    assert activityService._streaks(days, today) == (3, 3)
    assert activityService._streaks(days | {today}, today) == (4, 4)
    assert activityService._streaks(set(), today) == (0, 0)


def test_a_calendar_year_stops_today_and_the_default_opens_on_a_monday():
    tz = activityService.zone("Europe/Luxembourg")
    start, end = activityService.period(None, tz)
    assert start.weekday() == 0 and 364 <= (end - start).days <= 370
    assert activityService.period(2024, tz) == (date(2024, 1, 1), date(2024, 12, 31))
    assert activityService.zone("Not/AZone").key == "Europe/Luxembourg"


# =============================================================================
# End to end
# =============================================================================

ORG_A = "Activity org A"
ORG_B = "Activity org B"


@pytest.fixture(scope="module")
def people():
    org_a = ensure_org(ORG_A, modules=("bcl", "urr"))
    org_b = ensure_org(ORG_B, modules=("bcl",))
    return {
        "org_a": org_a, "org_b": org_b,
        "alice": login_as("alice@activity-a.lu", org_a, modules=("bcl", "urr")),
        "bob": login_as("bob@activity-a.lu", org_a, modules=("bcl",)),
        "admin_a": login_as("admin@activity-a.lu", org_a, role=Role.org_admin, modules=("bcl",)),
        "carol": login_as("carol@activity-b.lu", org_b, modules=("bcl",)),
        "platform": login_as("platform@activity.lu", org_b, role=Role.platform_admin, modules=()),
    }


def test_work_shows_on_the_users_own_dashboard(people):
    alice = people["alice"]
    result(alice.post("/api/v1/documents/bcl", json={"document_id": "ACT_A.xml", "label": "S 1.3"}))
    result(alice.post("/api/v1/drafts/urr", json={"name": "september", "data": {}}))
    assert alice.get("/api/v1/bcl/s13/reference/report/preview").status_code == 200
    # Screens only, and a refused request: none of these is work.
    alice.get("/api/v1/urr/form")
    alice.post("/api/v1/documents/bcl/NOPE.xml/status", json={"status": "Approved"})

    mine = result(alice.get("/api/v1/activity/me", params={"tz": "Europe/Luxembourg"}))
    actions = {row["action"]: row["count"] for row in mine["by_action"]}
    # One sign-in (login_as), one filing, one draft, one workbook consulted.
    assert actions == {"signed_in": 1, "generated": 1, "drafted": 1, "consulted": 1}
    assert mine["total"] == 4 and mine["active_days"] == 1 and mine["current_streak"] == 1
    assert {row["module"] for row in mine["by_module"]} == {"bcl", "urr", "platform"}

    # The timeline names what was done: the filing and the draft.
    month = mine["months"][0]
    subjects = {s["subject"] for g in month["groups"] for s in g["subjects"]}
    assert {"ACT_A.xml", "september", "s13"} <= subjects
    assert month["groups"][0]["action"] == "generated"   # the filing leads the month
    assert mine["by_user"] == []                          # a user's own page lists no one else

    # Picking the day on the calendar narrows what is under it, not the calendar.
    today = mine["days"][-1][0]
    narrowed = result(alice.get("/api/v1/activity/me", params={"day": today, "module": "bcl"}))
    assert narrowed["shown_total"] == 2 and narrowed["day"] == today


def test_a_review_decision_is_recorded_for_the_reviewer(people):
    alice, bob = people["alice"], people["bob"]
    result(alice.post("/api/v1/documents/bcl", json={"document_id": "ACT_REVIEW.xml", "label": "S 1.3"}))
    result(alice.post("/api/v1/documents/bcl/ACT_REVIEW.xml/status", json={"status": "Under review"}))
    result(bob.post("/api/v1/documents/bcl/ACT_REVIEW.xml/status", json={"status": "Approved"}))

    reviews = result(bob.get("/api/v1/activity/me", params={"action": "reviewed"}))
    assert reviews["total"] == 1
    assert reviews["recent"][0]["subject"] == "ACT_REVIEW.xml · Approved"


def test_a_user_cannot_open_the_organisation_dashboard(people):
    assert people["alice"].get("/api/v1/activity/organisations").status_code == 403
    assert people["alice"].get("/api/v1/activity/scopes").status_code == 403


def test_an_organisation_admin_sees_their_organisation_only(people):
    admin = people["admin_a"]
    result(people["carol"].post("/api/v1/documents/bcl", json={"document_id": "ACT_B.xml", "label": "S 1.3"}))

    scopes = result(admin.get("/api/v1/activity/scopes"))
    assert [scope["name"] for scope in scopes] == [ORG_A]

    seen = result(admin.get("/api/v1/activity/organisations"))
    names = {row["email"] for row in seen["by_user"]}
    assert "alice@activity-a.lu" in names and "carol@activity-b.lu" not in names

    # Another organisation, directly or through one of its users, is refused.
    assert admin.get("/api/v1/activity/organisations",
                     params={"organisation_id": people["org_b"]}).status_code == 403
    carol_id = next(u["id"] for s in result(people["platform"].get("/api/v1/activity/scopes"))
                    for u in s["users"] if u["email"] == "carol@activity-b.lu")
    assert admin.get("/api/v1/activity/organisations", params={"user_id": carol_id}).status_code == 404

    # One of their own users.
    alice_id = next(u["id"] for u in scopes[0]["users"] if u["email"] == "alice@activity-a.lu")
    alone = result(admin.get("/api/v1/activity/organisations", params={"user_id": alice_id}))
    assert [row["email"] for row in alone["by_user"]] == ["alice@activity-a.lu"]


def test_a_platform_admin_sees_every_organisation(people):
    platform = people["platform"]
    names = {scope["name"] for scope in result(platform.get("/api/v1/activity/scopes"))}
    assert {ORG_A, ORG_B} <= names

    everyone = result(platform.get("/api/v1/activity/organisations"))
    emails = {row["email"] for row in everyone["by_user"]}
    assert {"alice@activity-a.lu", "carol@activity-b.lu"} <= emails

    only_b = result(platform.get("/api/v1/activity/organisations", params={"organisation_id": people["org_b"]}))
    assert "alice@activity-a.lu" not in {row["email"] for row in only_b["by_user"]}
    assert only_b["by_organisation"] == []          # one organisation: no comparison to draw
    compared = {row["name"]: row for row in everyone["by_organisation"]}
    assert compared[ORG_A]["users"] >= 2 and compared[ORG_B]["count"] >= 1
