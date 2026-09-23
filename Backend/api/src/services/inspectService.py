"""Reading a filing back in.

BCL and AIFMD each identify an uploaded document against their own family of
schemas, because both have several. The other XML regimes produce one
document, so identifying it is simpler: parse it, look at its root, and
validate it against the regulator's schema where one is bundled.

Where no schema is bundled the answer says so rather than reporting the
document as valid. A filing that has only been checked for well-formedness
has not been checked against anything a regulator will apply, and saying
otherwise would be worse than saying nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.paths import RESOURCES_DIR

try:
    from lxml import etree as _etree
except ImportError:  # pragma: no cover - lxml is a declared dependency
    _etree = None


class _FolderResolver:  # pragma: no cover - replaced below when lxml is present
    pass


if _etree is not None:

    class _FolderResolver(_etree.Resolver):  # type: ignore[no-redef]
        """Resolves every xs:include / xs:import by file name inside the
        schema's own folder. libxml2 cannot resolve a relative schemaLocation
        on a UNC path, which is where this application usually runs from."""

        def __init__(self, folder: Path) -> None:
            super().__init__()
            self._folder = folder

        def resolve(self, system_url, public_id, context):  # noqa: D401
            name = str(system_url).replace("\\", "/").rsplit("/", 1)[-1]
            candidate = self._folder / name
            if candidate.is_file():
                return self.resolve_string(candidate.read_bytes(), context)
            return None


#: The XML-producing regimes handled here, with the schema to check against
#: and the root element the regulator expects. A regime with no schema is
#: still listed: the point is to read the document back, and saying "no
#: schema is bundled for this one" is information the preparer needs.
REGIMES: dict[str, dict[str, Any]] = {
    "urr": {
        "label": "U 1.1 filing",
        "schema": RESOURCES_DIR / "regulation" / "urr" / "xsd" / "extracted" / "U11.xsd",
        "root": "U11",
        "note": "Validated against the CSSF U 1.1 schema.",
    },
    "fatca": {
        "label": "FATCA / CRS return",
        "schema": None,
        "root": None,
        "note": "The AEOI schemas are not bundled, so the document is read and identified "
                "but not validated. Validate it on the tax authority's own portal.",
    },
    "esef": {
        "label": "Inline XBRL report",
        "schema": None,
        "root": None,
        "note": "An ESEF report is checked by an XBRL processor against the conformance suite, "
                "not by an XSD. The document is read and identified only.",
    },
}


def _result(recognised: bool, label: str | None, root: str | None, namespace: str | None,
            available: bool, valid: bool, errors: list[str], detail: str | None) -> dict[str, Any]:
    return {
        "recognised": recognised,
        "label": label,
        "report_key": None,
        "file_key": None,
        "filename": None,
        "root": root,
        "namespace": namespace,
        "schema_validation": {
            "available": available, "valid": valid, "errors": errors, "detail": detail,
        },
    }


def inspect_service(regime_key: str, content: bytes) -> dict[str, Any]:
    """Identifies an uploaded filing and, where a schema exists, validates it."""
    regime = REGIMES.get(regime_key)
    if regime is None:
        raise LookupError(f"'{regime_key}' does not produce an XML filing that can be read back.")

    if _etree is None:
        return _result(False, None, None, None, False, False, [],
                       "XSD validation unavailable: install lxml.")

    try:
        document = _etree.fromstring(content)
    except _etree.XMLSyntaxError as exc:
        return _result(False, None, None, None, False, False,
                       [f"Not well-formed XML: {exc}"], None)

    qualified = _etree.QName(document)
    root, namespace = qualified.localname, qualified.namespace or ""

    expected = regime["root"]
    if expected and root != expected:
        return _result(
            False, None, root, namespace, False, False,
            [f"The root element is <{root}>, not <{expected}>: this is not a {regime['label']}."],
            None)

    schema_path: Path | None = regime["schema"]
    if schema_path is None or not schema_path.is_file():
        missing = schema_path is not None
        return _result(
            True, regime["label"], root, namespace,
            available=False, valid=False, errors=[],
            detail=("The schema is referenced but not bundled, so the document could not be "
                    "validated." if missing else regime["note"]))

    parser = _etree.XMLParser()
    parser.resolvers.add(_FolderResolver(schema_path.parent))
    schema = _etree.XMLSchema(_etree.parse(str(schema_path), parser))

    valid = schema.validate(document)
    errors = [f"line {e.line}: {e.message}" for e in schema.error_log]
    return _result(True, regime["label"], root, namespace,
                   available=True, valid=valid, errors=errors,
                   detail=regime["note"] if valid else None)
