"""Validation of generated BCL XML against the official BCL XSD schemas.

The six schemas (S13, S213, S16, S44, S220, SBS.OBS + their datatypes /
structures companions) are bundled unmodified under core/bcl_schemas/<report>/
— a copy of the folders provided by BCL in BCL/<report>/. Validation needs
``lxml``; if it is not installed the functions degrade gracefully (they report
"XSD validation unavailable" instead of raising) so the rest of the module
keeps working.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# report key -> (sub-folder, main schema file)
SCHEMAS: dict[str, tuple[str, str]] = {
    "s13": ("s13", "S13.xsd"),
    "s213": ("s213", "S213.xsd"),
    "s16": ("s16", "S16.xsd"),
    "s44": ("s44", "S44.xsd"),
    "s220": ("s220", "S220.xsd"),
    "tptobs": ("tptobs", "SBS.OBS.xsd"),
}

# (root element local name, namespace) -> report key, read from the schemas
ROOTS: dict[tuple[str, str], str] = {
    ("S13", "http://www.bcl.lu/2008/S1.3"): "s13",
    ("S213", "http://www.bcl.lu/2008/S2.13"): "s213",
    ("S16", "http://www.bcl.lu/2008/S1.6"): "s16",
    ("S44", "http://www.bcl.lu/2024/S4.4"): "s44",
    ("S220", "http://www.bcl.lu/2025/S2.20"): "s220",
    ("SBS", "http://www.bcl.lu/2007/SBS"): "tptobs",
}

try:  # pragma: no cover - import guard
    from lxml import etree as _etree
except ImportError:  # pragma: no cover
    _etree = None


def available() -> bool:
    return _etree is not None


@dataclass
class XsdResult:
    report_key: str | None
    valid: bool
    errors: list[str]
    available: bool = True
    detail: str = ""


def _to_bytes(xml: str | bytes) -> bytes:
    return xml.encode("utf-8") if isinstance(xml, str) else xml


if _etree is not None:
    class _FolderResolver(_etree.Resolver):
        """Resolves every xs:include / xs:import by *file name* inside the
        report's own schema folder. libxml2 cannot resolve relative
        schemaLocation on UNC paths (\\\\server\\share\\...), which is exactly
        where this app usually runs from (mapped network drive), and it would
        also make validation depend on the current working directory."""

        def __init__(self, folder: Path) -> None:
            super().__init__()
            self._folder = folder

        def resolve(self, system_url, public_id, context):  # noqa: D401
            name = str(system_url).replace("\\", "/").rsplit("/", 1)[-1]
            candidate = self._folder / name
            if candidate.is_file():
                return self.resolve_string(candidate.read_bytes(), context)
            return None


@lru_cache(maxsize=None)
def _schema(report_key: str):
    folder, main = SCHEMAS[report_key]
    schema_folder = SCHEMA_DIR / folder
    parser = _etree.XMLParser()
    parser.resolvers.add(_FolderResolver(schema_folder))
    doc = _etree.fromstring((schema_folder / main).read_bytes(), parser)
    return _etree.XMLSchema(doc)


def detect_report(xml: str | bytes) -> str | None:
    """Report key from the root element name + namespace (None if the document
    is not well formed or is not one of the six BCL reports)."""
    if _etree is None:
        return _detect_without_lxml(xml)
    try:
        root = _etree.fromstring(_to_bytes(xml))
    except _etree.XMLSyntaxError:
        return None
    return ROOTS.get((_etree.QName(root).localname, _etree.QName(root).namespace or ""))


def _detect_without_lxml(xml: str | bytes) -> str | None:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(_to_bytes(xml))
    except ET.ParseError:
        return None
    ns, _, local = root.tag[1:].partition("}") if root.tag.startswith("{") else ("", "", root.tag)
    return ROOTS.get((local, ns))


def validate(xml: str | bytes, report_key: str | None = None) -> XsdResult:
    """Validates ``xml`` against the schema of ``report_key`` (auto-detected from
    the document when omitted)."""
    if _etree is None:
        return XsdResult(report_key, False, [], available=False,
                         detail="XSD validation unavailable: install lxml (pip install lxml).")
    try:
        doc = _etree.fromstring(_to_bytes(xml))
    except _etree.XMLSyntaxError as exc:
        return XsdResult(report_key, False, [f"Not well-formed XML: {exc}"])
    detected = ROOTS.get((_etree.QName(doc).localname, _etree.QName(doc).namespace or ""))
    key = report_key or detected
    if key is None:
        return XsdResult(None, False, [
            f"Unrecognised root element {{{_etree.QName(doc).namespace}}}{_etree.QName(doc).localname}: "
            "not one of the six BCL reports (S13, S213, S16, S44, S220, SBS)."])
    if detected is not None and detected != key:
        return XsdResult(key, False, [
            f"Document root/namespace corresponds to report '{detected}', not '{key}'."])
    schema = _schema(key)
    ok = schema.validate(doc)
    errors = [f"line {e.line}: {e.message}" for e in schema.error_log] if not ok else []
    return XsdResult(key, ok, errors)
