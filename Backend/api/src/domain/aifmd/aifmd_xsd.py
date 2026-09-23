"""Validation of generated AIFMD Annex IV XML against the official ESMA XSDs.

The three schemas (AIFMD_DATMAN_V1.2.xsd for the manager file,
AIFMD_DATAIF_V1.2.xsd for the fund file, and the shared
AIFMD_REPORTING_DataTypes_V1.2.xsd they both include) are bundled unmodified
under core/aifmd_schemas/ — a copy of the ESMA reporting package at
AIFMD/AIFMD_reporting_it_technical_guidance/2013-1361_aifmd_reporting_xml_documents_v1.2/.

Both schemas are no-namespace schemas, so a report's root element carries no
namespace and the file is identified by its root element name alone
(AIFMReportingInfo or AIFReportingInfo). That is also what CSSF control
FOR-003 / FOR-004 checks: the file type in the name must match the XML.

Validation needs ``lxml``; if it is not installed the functions degrade
gracefully rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# file key -> (main schema file, root element name, the "type of file" token
# used by the CSSF naming convention)
SCHEMAS: dict[str, tuple[str, str, str]] = {
    "datman": ("AIFMD_DATMAN_V1.2.xsd", "AIFMReportingInfo", "MAN"),
    "dataif": ("AIFMD_DATAIF_V1.2.xsd", "AIFReportingInfo", "AIF"),
}

ROOTS: dict[str, str] = {root: key for key, (_, root, _) in SCHEMAS.items()}

FILE_LABELS: dict[str, str] = {
    "datman": "AIFM file (DATMAN)",
    "dataif": "AIF file (DATAIF)",
}

try:  # pragma: no cover - import guard
    from lxml import etree as _etree
except ImportError:  # pragma: no cover
    _etree = None


def available() -> bool:
    return _etree is not None


@dataclass
class XsdResult:
    file_key: str | None
    valid: bool
    errors: list[str]
    available: bool = True
    detail: str = ""


def _to_bytes(xml: str | bytes) -> bytes:
    return xml.encode("utf-8") if isinstance(xml, str) else xml


if _etree is not None:
    class _FolderResolver(_etree.Resolver):
        """Resolves every xs:include by file name inside core/aifmd_schemas/.
        libxml2 cannot resolve a relative schemaLocation on a UNC path
        (\\\\server\\share\\...), which is exactly where this app usually runs
        from, and it would otherwise depend on the working directory."""

        def resolve(self, system_url, public_id, context):  # noqa: D401
            name = str(system_url).replace("\\", "/").rsplit("/", 1)[-1]
            candidate = SCHEMA_DIR / name
            if candidate.is_file():
                return self.resolve_string(candidate.read_bytes(), context)
            return None


@lru_cache(maxsize=None)
def _schema(file_key: str):
    main, _root, _token = SCHEMAS[file_key]
    parser = _etree.XMLParser()
    parser.resolvers.add(_FolderResolver())
    doc = _etree.fromstring((SCHEMA_DIR / main).read_bytes(), parser)
    return _etree.XMLSchema(doc)


def _root_name(xml: str | bytes) -> str | None:
    if _etree is not None:
        try:
            root = _etree.fromstring(_to_bytes(xml))
        except _etree.XMLSyntaxError:
            return None
        return _etree.QName(root).localname
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(_to_bytes(xml))
    except ET.ParseError:
        return None
    return root.tag.rpartition("}")[2]


def detect_file(xml: str | bytes) -> str | None:
    """'datman', 'dataif', or None when the document is not well formed or is
    not an AIFMD Annex IV report."""
    name = _root_name(xml)
    return ROOTS.get(name) if name else None


def validate(xml: str | bytes, file_key: str | None = None) -> XsdResult:
    """Validates ``xml`` against the ESMA schema of ``file_key`` (auto-detected
    from the root element when omitted)."""
    if _etree is None:
        return XsdResult(file_key, False, [], available=False,
                         detail="XSD validation unavailable: install lxml (pip install lxml).")
    try:
        doc = _etree.fromstring(_to_bytes(xml))
    except _etree.XMLSyntaxError as exc:
        return XsdResult(file_key, False, [f"Not well-formed XML: {exc}"])

    detected = ROOTS.get(_etree.QName(doc).localname)
    key = file_key or detected
    if key is None:
        return XsdResult(None, False, [
            f"Unrecognised root element {_etree.QName(doc).localname!r}: an AIFMD Annex IV file must be "
            f"AIFMReportingInfo (AIFM file) or AIFReportingInfo (AIF file)."])
    if detected is not None and detected != key:
        return XsdResult(key, False, [
            f"The document is a {FILE_LABELS[detected]}, not a {FILE_LABELS[key]} "
            f"(CSSF controls FOR-003 / FOR-004)."])

    schema = _schema(key)
    ok = schema.validate(doc)
    errors = [f"line {e.line}: {e.message}" for e in schema.error_log] if not ok else []
    return XsdResult(key, ok, errors)


def record_count(xml: str | bytes) -> int:
    """Number of reporting records in the document. CSSF control FOR-010
    refuses a file carrying more than one."""
    name = _root_name(xml)
    if name is None:
        return 0
    if _etree is not None:
        root = _etree.fromstring(_to_bytes(xml))
    else:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(_to_bytes(xml))
    wanted = {"AIFMRecordInfo", "CancellationAIFMRecordInfo", "AIFRecordInfo", "CancellationAIFRecordInfo"}
    return sum(1 for child in root if str(getattr(child, "tag", "")).rpartition("}")[2] in wanted)
