"""Non-regression against the Streamlit MVP.

For every case of ``non_regression/cases.py``, the API must produce what the
Streamlit tool produced for the same input — the same filing, byte for byte
once production timestamps are masked, the same file name, or the same
refusal with the same reasons. The expected outputs were built by running
the Streamlit code itself (``non_regression/oracle.py``); the Streamlit
project does not need to be on disk to run this suite.

A failure here means the migration changed what a preparer would file. If
the change is deliberate, re-anchor the reference with the oracle and say
why in the commit.
"""

from __future__ import annotations

import base64
import difflib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent / "non_regression"))

import cases as case_catalogue  # noqa: E402
import normalize  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)
API = "/api/v1"


def _result(response) -> dict:
    payload = response.json()
    assert payload.get("success") is True, f"HTTP {response.status_code}: {payload.get('message')}"
    return payload["result"]


# =============================================================================
# The API's answer, in the shape the oracle wrote
# =============================================================================

def _filing(regime: str, answer: dict) -> dict:
    if not answer["generated"]:
        return {"generated": False, "errors": answer["errors"], "files": []}
    if answer.get("content_base64"):
        produced = {"filename": normalize.filename(answer["filename"]),
                    "cells": normalize.workbook(base64.b64decode(answer["content_base64"]))}
    else:
        produced = {"filename": normalize.filename(answer["filename"]),
                    "content": normalize.text(answer["content"])}
    return {"generated": True, "errors": [], "files": [produced]}


def _generation(answer: dict) -> dict:
    """BCL and AIFMD answer with a GenerationResult."""
    if not answer["generated"]:
        return {"generated": False, "files": [],
                "errors": [[issue["code"], issue["message"]] for issue in answer["validation"]["errors"]]}
    return {"generated": True, "errors": [], "files": [
        {"filename": normalize.filename(f["filename"]), "content": normalize.text(f["content"]),
         "schema_valid": f["schema_validation"]["valid"]}
        for f in answer["files"]]}


def actual(case: dict) -> dict:
    kind = case["kind"]
    if kind == "filing_draft":
        return _filing(case["regime"], _result(client.post(f"{API}/{case['regime']}/generate", json=case["draft"])))
    if kind == "filing_workbook":
        content = (case_catalogue.INPUTS / case["input"]).read_bytes()
        draft = _result(client.post(f"{API}/{case['regime']}/parse", files={"file": (case["input"], content)}))
        assert draft.pop("errors") == [], "the filled-in template should parse cleanly"
        return _filing(case["regime"], _result(client.post(f"{API}/{case['regime']}/generate", json=draft)))
    if kind == "bcl":
        return _generation(_result(client.post(f"{API}/bcl/{case['report']}/generate", json=case["draft"])))
    if kind == "aifmd":
        return _generation(_result(client.post(f"{API}/aifmd/generate", json=case["draft"])))
    if kind == "priips":
        calculation = _result(client.post(f"{API}/priips/calculate", json={"fund": case["fund"]}))
        kid = _result(client.post(f"{API}/priips/kid", json={"fund": case["fund"]}))
        data = {"sri": calculation["sri"], "costs": calculation["costs"],
                "scenarios": calculation["scenarios"], "kid": kid}
        return {"generated": True, "errors": [], "files": [], "data": normalize.data(data)}
    if kind == "fatca":
        content = (case_catalogue.INPUTS / case["input"]).read_bytes()
        answer = _result(client.post(
            f"{API}/fatca/generate", files={"file": (case["input"], content)},
            data={"parameters": json.dumps(case["parameters"]), "preparer": case["preparer"]}))
        if not answer["files"]:
            return {"generated": False, "errors": answer["errors"], "files": []}
        return {"generated": True, "errors": [], "files": [
            {"filename": normalize.filename(f["filename"]), "content": normalize.text(f["content"])}
            for f in answer["files"]]}
    raise LookupError(kind)


# =============================================================================
# The comparison
# =============================================================================

def _explain(expected: dict, got: dict) -> str:
    """A readable account of the first difference, rather than two dumps."""
    if expected["generated"] != got["generated"]:
        return (f"Streamlit {'generated' if expected['generated'] else 'refused'} this filing, "
                f"the API {'generated' if got['generated'] else 'refused'} it.\n"
                f"  Streamlit errors: {expected['errors']}\n  API errors:       {got['errors']}")
    if expected["errors"] != got["errors"]:
        return f"Different refusal.\n  Streamlit: {expected['errors']}\n  API:       {got['errors']}"
    for want, have in zip(expected["files"], got["files"]):
        if want.get("filename") != have.get("filename"):
            return f"File name: Streamlit {want.get('filename')!r}, API {have.get('filename')!r}"
        if "content" in want and want["content"] != have.get("content"):
            diff = difflib.unified_diff(want["content"].splitlines(), (have.get("content") or "").splitlines(),
                                        "streamlit", "api", lineterm="", n=2)
            return "Content differs:\n" + "\n".join(list(diff)[:40])
        if want != have:
            return f"File differs:\n  Streamlit: {json.dumps(want)[:600]}\n  API:       {json.dumps(have)[:600]}"
    if len(expected["files"]) != len(got["files"]):
        return f"Streamlit produced {len(expected['files'])} file(s), the API {len(got['files'])}."
    return (f"Data differs:\n  Streamlit: {json.dumps(expected.get('data'))[:800]}\n"
            f"  API:       {json.dumps(got.get('data'))[:800]}")


CASES = case_catalogue.all_cases()


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_same_output_as_the_streamlit_mvp(case):
    reference = case_catalogue.REFERENCE / f"{case['id']}.json"
    assert reference.exists(), f"No reference for {case['id']}: run non_regression/oracle.py"
    expected = json.loads(reference.read_text(encoding="utf-8"))
    got = json.loads(json.dumps(case_catalogue.jsonable(actual(case)), sort_keys=True))
    assert got == expected, _explain(expected, got)


def test_every_reference_has_a_case():
    """A reference without its case is a check that silently stopped running."""
    ids = {case["id"] for case in CASES}
    references = {path.stem for path in case_catalogue.REFERENCE.glob("*.json") if not path.stem.startswith("_")}
    assert references == ids
