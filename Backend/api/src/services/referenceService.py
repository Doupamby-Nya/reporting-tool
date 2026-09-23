"""Reference data shared across the regimes.

The catalogue of regulatory modules the platform supports, the regulator
documents bundled with each of them, and the client records a filing is
prepared for.
"""

from __future__ import annotations

from typing import Any

from domain.shared import clients, regulation_library

# One entry per regulatory module, in the order the platform presents them.
MODULES: list[dict[str, Any]] = [
    {"key": "priips", "label": "PRIIPs KID", "authority": "EU / CSSF",
     "description": "Key Information Document under Regulation (EU) 1286/2014, with the SRI, cost and "
                    "performance-scenario calculations of the RTS.",
     "outputs": ["PDF", "DOCX"]},
    {"key": "fatca", "label": "FATCA & CRS", "authority": "ACD Luxembourg",
     "description": "Automatic exchange of information: account classification and the FATCA/CRS XML returns.",
     "outputs": ["XML"]},
    {"key": "urr", "label": "U 1.1", "authority": "CSSF",
     "description": "Monthly financial information on undertakings for collective investment.",
     "outputs": ["XML"]},
    {"key": "o41", "label": "O 4.1", "authority": "CSSF / BCL",
     "description": "Balance-sheet statistics under Circular IML 97/136, filed as EDIFACT.",
     "outputs": ["EDIFACT"]},
    {"key": "esef", "label": "ESEF", "authority": "ESMA",
     "description": "Annual financial report in Inline XBRL, packaged as an ESEF report package.",
     "outputs": ["iXBRL", "ZIP"]},
    {"key": "aifmd", "label": "AIFMD Annex IV", "authority": "CSSF / ESMA",
     "description": "AIFM-level and AIF-level reporting under Articles 3(3)(d), 24(1), 24(2) and 24(4).",
     "outputs": ["XML"]},
    {"key": "saq", "label": "SAQ", "authority": "CSSF",
     "description": "Self-assessment questionnaire of Circular CSSF 21/790.",
     "outputs": ["XLSX"]},
    {"key": "bcl", "label": "BCL statistical reports", "authority": "Banque centrale du Luxembourg",
     "description": "S 1.3, S 2.13, S 1.6, S 2.20, S 4.4 and TPTOBS Layout 3.",
     "outputs": ["XML"]},
]


def modules_service() -> list[dict[str, Any]]:
    return MODULES


def regulations_service(module_key: str) -> list[dict[str, Any]]:
    """The regulator documents bundled for one module."""
    documents = regulation_library.docs_for(module_key)
    if not documents:
        raise LookupError(f"No regulatory library is bundled for module '{module_key}'.")
    return [
        {
            "index": index, "title": doc.title, "issuer": doc.issuer,
            "description": doc.description, "filename": (doc.file or "").rsplit("/", 1)[-1],
            "url": doc.url,
            "downloadable": regulation_library.doc_bytes(doc) is not None,
        }
        for index, doc in enumerate(documents)
    ]


def regulation_document_service(module_key: str, index: int) -> tuple[str, bytes]:
    documents = regulation_library.docs_for(module_key)
    if not 0 <= index < len(documents):
        raise LookupError(f"Module '{module_key}' has no regulatory document at position {index}.")
    doc = documents[index]
    payload = regulation_library.doc_bytes(doc)
    if payload is None:
        raise LookupError(f"The document '{doc.title}' is referenced but its file is not bundled.")
    return (doc.file or "document.pdf").rsplit("/", 1)[-1], payload


def clients_service() -> list[dict[str, Any]]:
    """The client records a filing can be prepared for."""
    return clients.get_all_clients()
