"""Who did what, where and when: the platform's activity record.

Every successful request a signed-in user makes is matched against the
table below; the ones that stand for work (a filing generated, a review
decision, a workbook ingested, a draft saved, a text consulted) become an
ActivityEvent. Reads that only draw a screen — a form, a code list — are not
activity and are not kept.

The dashboards read it back as one summary, whatever the scope: a user's
own usage, one organisation, one of its users, one module. The calendar is
counted in the viewer's time zone, so an evening's work lands on the day it
was done rather than on the next UTC day.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session, col, select

from database.db import engine
from database.tables import ActivityEvent, Organisation, User

DEFAULT_TZ = "Europe/Luxembourg"

#: action -> (label for a breakdown, one of them, several of them)
ACTIONS: dict[str, tuple[str, str, str]] = {
    "generated": ("Filings generated", "filing generated", "filings generated"),
    "reviewed": ("Review decisions", "review decision", "review decisions"),
    "validated": ("Controls run", "control run", "control runs"),
    "ingested": ("Files ingested", "file ingested", "files ingested"),
    "drafted": ("Drafts saved", "draft saved", "drafts saved"),
    "deleted": ("Drafts deleted", "draft deleted", "drafts deleted"),
    "consulted": ("Texts consulted", "text consulted", "texts consulted"),
    "downloaded": ("Files downloaded", "file downloaded", "files downloaded"),
    "configured": ("Settings changed", "setting changed", "settings changed"),
    "signed_in": ("Sign-ins", "sign-in", "sign-ins"),
    "administered": ("Administration", "administration change", "administration changes"),
}

#: The order the timeline groups a month's work in: the filing first.
ACTION_ORDER = list(ACTIONS)

_MODULE = r"(?P<module>priips|fatca|urr|o41|esef|aifmd|saq|bcl)"

#: (method, path under /api/v1, action). The module comes from the
#: path's `module` group, or is given as a fourth element.
_RULES: list[tuple[str, re.Pattern[str], str, str | None]] = [
    (method, re.compile(f"^{pattern}$"), action, module)
    for method, pattern, action, module in [
        # The filing itself: registered once generated, then reviewed.
        ("POST", rf"/documents/{_MODULE}", "generated", None),
        ("POST", rf"/documents/{_MODULE}/(?P<subject>[^/]+)/status", "reviewed", None),
        ("POST", r"/fatca/notifications", "generated", "fatca"),
        # Controls: validations, cross-checks, calculations, classification.
        ("POST", rf"/{_MODULE}/validate", "validated", None),
        ("POST", rf"/bcl/(?P<subject>[^/]+)/validate", "validated", "bcl"),
        ("POST", r"/bcl/cross-checks", "validated", "bcl"),
        ("POST", r"/priips/calculate", "validated", "priips"),
        ("POST", r"/fatca/classify", "validated", "fatca"),
        # Files brought in: a filing re-opened, a workbook read.
        ("POST", rf"/{_MODULE}/inspect", "ingested", None),
        ("POST", rf"/{_MODULE}/(template/)?parse", "ingested", None),
        ("POST", r"/funds/parse", "ingested", "funds"),
        # Drafts.
        ("POST", rf"/drafts/{_MODULE}", "drafted", None),
        ("DELETE", rf"/drafts/{_MODULE}/(?P<subject>[^/]+)", "deleted", None),
        # The regulator's texts and templates.
        ("GET", rf"/reference/regulations/{_MODULE}/\d+/download", "consulted", None),
        ("GET", r"/reference/regulations/chain/\d+/download", "consulted", "priips"),
        ("GET", r"/bcl/(?P<subject>[^/]+)/reference/[a-z]+/preview", "consulted", "bcl"),
        ("GET", r"/bcl/(?P<subject>[^/]+)/reference/[a-z]+", "consulted", "bcl"),
        ("GET", rf"/{_MODULE}/template", "downloaded", None),
        ("GET", r"/funds/template", "downloaded", "funds"),
        # Configuration.
        ("PUT", r"/fatca/preparers", "configured", "fatca"),
        ("PUT", r"/priips/(templates/[^/]+|parameters|settings)", "configured", "priips"),
        ("POST", r"/priips/(templates/[^/]+|parameters)/reset", "configured", "priips"),
        ("POST", r"/funds(/demo)?", "configured", "funds"),
        ("DELETE", r"/funds(/[^/]+)?", "configured", "funds"),
        # The platform itself.
        ("POST", r"/auth/login", "signed_in", "platform"),
        ("POST", r"/admin/.+", "administered", "platform"),
        ("PUT", r"/admin/.+", "administered", "platform"),
    ]
]

API_PREFIX = "/api/v1"


def classify(method: str, path: str, query: dict[str, str] | None = None) -> tuple[str, str, str | None] | None:
    """(module, action, subject) for a request that counts as activity."""
    if not path.startswith(API_PREFIX):
        return None
    local = path[len(API_PREFIX):].rstrip("/")
    for rule_method, pattern, action, module in _RULES:
        if rule_method != method:
            continue
        found = pattern.match(local)
        if not found:
            continue
        groups = found.groupdict()
        subject = groups.get("subject")
        # A PDF saved to disk is a download; one shown in the page is a read.
        if action == "consulted" and (query or {}).get("download") == "true":
            action = "downloaded"
        if action == "consulted" and "/bcl/" in local and "/preview" not in local \
                and (query or {}).get("inline") != "true":
            action = "downloaded"
        return module or groups["module"], action, subject
    return None


def capture(user: Any, method: str, path: str, query: dict[str, str], status_code: int,
            subject: str | None = None) -> None:
    """Records one request as activity, if it is. Never raises: a failure to
    log must not become a failure of the work that was just done."""
    try:
        if user is None or status_code >= 400:
            return
        found = classify(method, path, query)
        if found is None:
            return
        module, action, derived = found
        with Session(engine) as db:
            db.add(ActivityEvent(occurred_at=datetime.now(UTC), organisation_id=user.organisation_id,
                                 user_id=user.id, module=module, action=action,
                                 subject=subject or derived or None, method=method, path=path[:300]))
            db.commit()
    except Exception:
        logging.exception("Recording activity failed")


# =============================================================================
# Reading it back
# =============================================================================

def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def period(year: int | None, tz: ZoneInfo) -> tuple[date, date]:
    """A calendar year, or — like GitHub's default — the 52 weeks and a day
    to today, starting on a Monday so the grid opens on a full column."""
    today = datetime.now(tz).date()
    if year:
        # The current year stops at today: the days after it are not empty, just not yet.
        return date(year, 1, 1), min(date(year, 12, 31), today)
    start = today - timedelta(days=364)
    return start - timedelta(days=start.weekday()), today


def _streaks(days: set[date], today: date) -> tuple[int, int]:
    longest = run = 0
    previous: date | None = None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    # The current streak still counts when today is not over yet.
    current, cursor = 0, today if today in days else today - timedelta(days=1)
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def summary(db: Session, *, organisation_id: int | None = None, user_id: int | None = None,
            module: str | None = None, action: str | None = None, year: int | None = None,
            day: date | None = None, tz_name: str | None = None, with_users: bool = False) -> dict[str, Any]:
    tz = zone(tz_name)
    start, end = period(year, tz)
    # The viewer's midnights, in UTC: that is how the events are stored.
    start_utc = datetime.combine(start, time.min, tz).astimezone(UTC)
    end_utc = datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(UTC)

    scope = select(ActivityEvent)
    if organisation_id is not None:
        scope = scope.where(ActivityEvent.organisation_id == organisation_id)
    if user_id is not None:
        scope = scope.where(ActivityEvent.user_id == user_id)
    if module:
        scope = scope.where(ActivityEvent.module == module)
    if action:
        scope = scope.where(ActivityEvent.action == action)

    # The years the selector offers: every year this scope has any activity in.
    first = db.exec(scope.order_by(col(ActivityEvent.occurred_at)).limit(1)).first()
    this_year = datetime.now(tz).year
    years = list(range(this_year, (_local(first.occurred_at, tz).year if first else this_year) - 1, -1))

    events = db.exec(scope.where(ActivityEvent.occurred_at >= start_utc, ActivityEvent.occurred_at < end_utc)
                     .order_by(col(ActivityEvent.occurred_at).desc())).all()

    per_day: Counter[date] = Counter(_local(event.occurred_at, tz).date() for event in events)
    current, longest = _streaks(set(per_day), datetime.now(tz).date())
    busiest = max(per_day.items(), key=lambda item: (item[1], item[0]), default=None)

    # Everything under the calendar follows the day picked on it, if any.
    shown = [event for event in events if _local(event.occurred_at, tz).date() == day] if day else events

    users = _users(db, {event.user_id for event in shown}) if (with_users or shown) else {}

    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "timezone": str(tz.key),
        "years": years,
        "day": day.isoformat() if day else None,
        "total": len(events),
        "days": [[d.isoformat(), n] for d, n in sorted(per_day.items())],
        "active_days": len(per_day),
        "current_streak": current,
        "longest_streak": longest,
        "busiest_day": {"date": busiest[0].isoformat(), "count": busiest[1]} if busiest else None,
        "shown_total": len(shown),
        "by_module": _ranked(Counter(event.module for event in shown), "module"),
        "by_action": _ranked(Counter(event.action for event in shown), "action"),
        "by_hour": _by_hour(shown, tz),
        "by_user": _by_user(shown, users, tz) if with_users else [],
        # Across organisations only: a platform administrator's view of all of them.
        "by_organisation": _by_organisation(db, shown) if with_users and organisation_id is None else [],
        "months": _months(shown, tz),
        "recent": [_describe(event, users, tz) for event in shown[:25]],
    }


def _local(moment: datetime, tz: ZoneInfo) -> datetime:
    return moment.replace(tzinfo=UTC).astimezone(tz) if moment.tzinfo is None else moment.astimezone(tz)


def _ranked(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [{key: name, "count": count} for name, count in counter.most_common()]


def _by_hour(events: list[ActivityEvent], tz: ZoneInfo) -> list[list[int]]:
    """Weekday (Monday first) x hour of day: when the work gets done."""
    grid = [[0] * 24 for _ in range(7)]
    for event in events:
        moment = _local(event.occurred_at, tz)
        grid[moment.weekday()][moment.hour] += 1
    return grid


def _users(db: Session, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    return {user.id: user for user in db.exec(select(User).where(col(User.id).in_(ids))).all()}


def _by_user(events: list[ActivityEvent], users: dict[int, User], tz: ZoneInfo) -> list[dict[str, Any]]:
    grouped: dict[int, list[ActivityEvent]] = defaultdict(list)
    for event in events:
        grouped[event.user_id].append(event)
    rows = []
    for user_id, own in grouped.items():
        user = users.get(user_id)
        modules = Counter(event.module for event in own)
        rows.append({
            "user_id": user_id,
            "name": user.name if user else f"User {user_id}",
            "email": user.email if user else "",
            "count": len(own),
            "active_days": len({_local(event.occurred_at, tz).date() for event in own}),
            "generated": sum(1 for event in own if event.action == "generated"),
            "reviewed": sum(1 for event in own if event.action == "reviewed"),
            "top_module": modules.most_common(1)[0][0],
            "modules": _ranked(modules, "module"),
            # Events arrive newest first.
            "last_active": _local(own[0].occurred_at, tz).isoformat(timespec="minutes"),
        })
    return sorted(rows, key=lambda row: (-row["count"], row["name"]))


def _by_organisation(db: Session, events: list[ActivityEvent]) -> list[dict[str, Any]]:
    counts = Counter(event.organisation_id for event in events)
    users = defaultdict(set)
    for event in events:
        users[event.organisation_id].add(event.user_id)
    names = {o.id: o.name for o in db.exec(select(Organisation).where(col(Organisation.id).in_(list(counts)))).all()}
    return [{"organisation_id": org_id, "name": names.get(org_id, f"Organisation {org_id}"),
             "count": count, "users": len(users[org_id])} for org_id, count in counts.most_common()]


def _months(events: list[ActivityEvent], tz: ZoneInfo) -> list[dict[str, Any]]:
    """The timeline under the calendar, newest month first: per month, one
    group per kind of work, each broken down by module, with the latest few
    subjects named — "12 filings generated in 3 modules"."""
    months: dict[str, dict[str, list[ActivityEvent]]] = defaultdict(lambda: defaultdict(list))
    for event in events:
        months[_local(event.occurred_at, tz).strftime("%Y-%m")][event.action].append(event)
    timeline = []
    for month in sorted(months, reverse=True):
        groups = []
        for action in ACTION_ORDER:
            own = months[month].get(action)
            if not own:
                continue
            subjects = []
            for event in own:
                if event.subject and (event.module, event.subject) not in [(s["module"], s["subject"]) for s in subjects]:
                    subjects.append({"module": event.module, "subject": event.subject,
                                     "at": _local(event.occurred_at, tz).isoformat(timespec="minutes")})
                if len(subjects) == 6:
                    break
            groups.append({"action": action, "count": len(own),
                           "modules": _ranked(Counter(event.module for event in own), "module"),
                           "subjects": subjects})
        timeline.append({"month": month, "total": sum(g["count"] for g in groups), "groups": groups})
    return timeline


def _describe(event: ActivityEvent, users: dict[int, User], tz: ZoneInfo) -> dict[str, Any]:
    user = users.get(event.user_id)
    return {
        "at": _local(event.occurred_at, tz).isoformat(timespec="minutes"),
        "module": event.module, "action": event.action, "subject": event.subject,
        "user": user.name if user else None,
    }


def organisations_in_scope(db: Session, viewer: Any) -> list[dict[str, Any]]:
    """The organisations an administrator may look at, with their users."""
    query = select(Organisation).order_by(Organisation.name)
    if not viewer.is_platform_admin:
        query = query.where(Organisation.id == viewer.organisation_id)
    organisations = db.exec(query).all()
    users = db.exec(select(User).where(col(User.organisation_id).in_([o.id for o in organisations]))
                    .order_by(User.name)).all()
    return [{
        "id": organisation.id, "name": organisation.name, "kind": organisation.kind.value,
        "users": [{"id": user.id, "name": user.name, "email": user.email, "active": user.active}
                  for user in users if user.organisation_id == organisation.id],
    } for organisation in organisations]
