"""Reading a BCL filing back in, proved by a round trip.

A parser is only right if what it produces regenerates the document it came
from. So each of the regulator's own examples is parsed, fed back through
the generator, and the result compared with the original — element by
element, value by value.

Anything the platform deliberately derives rather than stores is excluded
and named: a total it recomputes from its detail is not something an import
should be able to contradict.

    cd Backend/api
    poetry run pytest tests/test_bcl_parser.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.bcl import bcl_parser  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

BCL = Path(r"S:\Risk Consulting\03. Projects\7 - AI\Regulatory reporting tool for third-party ManCos"
           r"\PRIIPS_KID_MVP_streamlit_v20260902\BCL")
S13_DIR = "S 1.3 & S2.13 \u00abBilan statistique des fonds d'investissement\u00bb"

EXAMPLES = {
    "s13": BCL / S13_DIR / "S13_L4_Schema_XML_v1_2_r91/examples"
                          "/S0103_L4_202512_B000000789_O001220003_20141009_001.xml",
    "s213": BCL / S13_DIR / "S213_L2_Schema_XML_v1_2_r91/examples"
                           "/S0213_L2_202512_B000000789_O001220003_20241128_001.xml",
    "s16": BCL / "S 1.6/S16_L2_Schema_XML_v1_2_r91/examples"
                 "/S0106_L2_202512_B000000789_O001220003_20260120_001.xml",
    "s220": BCL / "S 2.20/S220_L0_Schema_XML/examples"
                  "/S0220_L0_202512_B000000341_NAF66012345600001_20250701_001.xml",
    "s44": BCL / "S4.4/S0404_L0_XML_schema/examples"
                 "/S0404_L0_202512_B000000789_O001220003_20260101_001.xml",
    "tptobs": BCL / "TPTOBS Layout 3/TPTOBS_L3_Schema_XML_v1_5_r155/examples"
                    "/TPTOBS_L3_202512_B000000789_O001220003_20241017_001.xml",
}

#: Elements the platform derives rather than stores, so an imported filing
#: cannot carry a value that contradicts the detail underneath it.
DERIVED = {
    "totalReportedAmount",  # TPTOBS: the sum of the securities on that line
    "layout",               # fixed per report
}

needs_examples = pytest.mark.skipif(
    not all(path.is_file() for path in EXAMPLES.values()),
    reason="BCL's own example files are not reachable from this machine")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def facts(root: ET.Element) -> dict[str, list[str]]:
    """Every leaf value in the document, keyed by its path. Values are
    grouped because a path repeats — one entry per reported line."""
    collected: dict[str, list[str]] = {}

    def walk(node: ET.Element, prefix: str = "") -> None:
        here = f"{prefix}/{local(node.tag)}"
        if len(node) == 0:
            if local(node.tag) not in DERIVED:
                collected.setdefault(here, []).append((node.text or "").strip())
        for child in node:
            walk(child, here)

    walk(root)
    return collected


def regenerate(report_key: str, captured: dict) -> str:
    """Feeds a parsed filing back through the generator it came from."""
    if report_key in ("s13", "s213", "s16"):
        body = {
            "header": captured["header"],
            "assets": [{"item": item, **row} for item, rows in captured["assets"].items()
                       for row in rows],
            "liabilities": [{"item": item, **row}
                            for item, rows in captured["liabilities"].items() for row in rows],
        }
    elif report_key == "s44":
        body = {"header": captured["s44"]["header"],
                "marketing_countries": [{"item": "2-004000", **row}
                                        for row in captured["s44"]["marketing_countries"]]}
    elif report_key == "tptobs":
        body = captured["tptobs"]
    else:
        s220 = captured["s220"]
        body = {**s220["scalars"],
                "sender_employees": s220["sender_employees"],
                "share_classes": s220["share_classes"]}

    response = client.post(f"/api/v1/bcl/{report_key}/generate", json=body)
    payload = response.json()
    assert payload["success"] is True, payload.get("message")
    outcome = payload["result"]
    assert outcome["generated"] is True, [
        f"{e['code']}: {e['message']}" for e in outcome["validation"]["errors"]]
    return outcome["files"][0]["content"]


@needs_examples
@pytest.mark.parametrize("report_key", sorted(EXAMPLES))
def test_an_official_example_is_recognised_and_read(report_key):
    detected, captured = bcl_parser.parse(EXAMPLES[report_key].read_bytes())
    assert detected == report_key
    assert captured is not None and captured["report_key"] == report_key


@needs_examples
@pytest.mark.parametrize("report_key", sorted(EXAMPLES))
def test_parsing_then_regenerating_reproduces_the_original(report_key):
    """The round trip. If a field were dropped on the way in, the regenerated
    document would differ from the regulator's own example here."""
    original = EXAMPLES[report_key].read_bytes()
    _, captured = bcl_parser.parse(original)
    rebuilt = regenerate(report_key, captured)

    theirs = facts(ET.fromstring(original))
    ours = facts(ET.fromstring(rebuilt))

    # An element the example writes empty and we omit carries no value, so
    # nothing is lost — and both documents satisfy the schema, which is what
    # the regulator checks. A path missing with a *value* behind it would be
    # a genuine loss, and is still caught.
    missing = {path: values for path, values in theirs.items()
               if path not in ours and any(value for value in values)}
    assert not missing, f"{len(missing)} element(s) lost on import: {sorted(missing)[:5]}"

    # Compared as multisets: the generator writes a report's lines in the
    # order of its chart of accounts, while an example may interleave them.
    # That is a presentation difference — the same lines, carrying the same
    # values — and it is what the XSD accepts from both.
    differing = {path: (values, ours[path]) for path, values in theirs.items()
                 if path in ours and sorted(values) != sorted(ours[path])}
    assert not differing, (
        f"{len(differing)} element(s) came back with different values: "
        f"{list(differing.items())[:3]}")


@needs_examples
def test_a_foreign_document_is_not_mistaken_for_a_filing():
    detected, captured = bcl_parser.parse(b"<Something xmlns='urn:x'><x/></Something>")
    assert detected is None and captured is None


@needs_examples
def test_the_upload_route_returns_the_captured_form():
    """What the screen needs: the upload answers with the data, not only a
    verdict on it."""
    path = EXAMPLES["s13"]
    response = client.post("/api/v1/bcl/inspect",
                           files={"file": (path.name, path.read_bytes(), "application/xml")})
    found = response.json()["result"]
    assert found["recognised"] is True
    assert found["data"]["header"]["reporter_code"]
    assert found["data"]["assets"], "no captured lines to pre-fill the form with"
