"""FATCA and CRS automatic exchange of information.

A filing starts from the reporting workbook: the accounts are classified
against the FATCA and CRS rules, and the resulting XML returns are built for
the Luxembourg tax authority.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from domain.fatca import fatca_pipeline
from domain.fatca.lib import core_functions_data_notification as notifications
from utils.paths import RESOURCES_DIR


def fatca_preparers_service() -> dict[str, Any]:
    """The preparer records a return can be filed under."""
    return fatca_pipeline.load_preparers()


def fatca_save_preparers_service(preparers: dict[str, dict[str, str]]) -> dict[str, Any]:
    fatca_pipeline.save_preparers(preparers)
    return fatca_pipeline.load_preparers()


def fatca_template_service(reporting_year: int | None = None) -> tuple[str, bytes, str]:
    """The blank reporting workbook, with the columns of the requested year."""
    payload = fatca_pipeline.build_fatca_template_workbook(reporting_year)
    name = f"FATCA_CRS_template{'_' + str(reporting_year) if reporting_year else ''}.xlsx"
    return name, payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def fatca_classify_service(content: bytes, parameters: dict[str, Any]) -> dict[str, Any]:
    """Reads the workbook and classifies every account. The result says what
    would be reported, and why, before any XML is produced."""
    # The second value is the CPS / Individual / Active tabs matched by name,
    # which is what the Streamlit tool classified and generated from; the
    # first is every sheet under its own name, and a client workbook whose
    # tabs are called e.g. "CPS 2025" would be missed from it.
    _sheets, template_tabs = fatca_pipeline.load_workbook_tabs(content)
    result = fatca_pipeline.classify(template_tabs, parameters)
    return {
        "counts": getattr(result, "counts", {}),
        "accounts": getattr(result, "accounts", []),
        "messages": getattr(result, "messages", []),
        "warnings": getattr(result, "warnings", []),
    }


def fatca_generate_service(content: bytes, parameters: dict[str, Any],
                           preparer_name: str | None = None) -> dict[str, Any]:
    """Classifies and then builds the return.

    The generator needs three things, and the third is easy to miss: the
    workbook's tabs, the reporting parameters, and the preparer record — the
    depositor point of contact the return is filed under, which is looked up
    by name from the configured preparers rather than passed in by the
    client, so a return can never name a preparer that is not on file.

    A filing is one document per run: the regime, report type and selection
    in the parameters pick which one.
    """
    _sheets, template_tabs = fatca_pipeline.load_workbook_tabs(content)
    result = fatca_pipeline.classify(template_tabs, parameters)

    preparers = fatca_pipeline.load_preparers()
    if not preparers:
        raise LookupError("No preparer is configured; add one at the configuration step first.")
    if preparer_name and preparer_name not in preparers:
        raise LookupError(f"'{preparer_name}' is not one of the configured preparers.")
    preparer = preparers[preparer_name] if preparer_name else next(iter(preparers.values()))

    xml, filename, errors = fatca_pipeline.generate_xml(template_tabs, parameters, preparer)

    files = []
    if xml:
        files.append({
            "filename": filename or "aeoi_return.xml",
            "label": f"{parameters.get('crs_fatca', 'AEOI')} {parameters.get('report_type', '')}".strip(),
            "content": xml, "content_base64": None, "media_type": "application/xml",
        })
    return {
        "counts": getattr(result, "counts", {}),
        "errors": errors,
        "files": files,
    }


def fatca_filer_categories_service() -> list[str]:
    """The FATCA FI filer categories a return may declare. Only FATCA has
    them — a CRS return carries none."""
    return list(fatca_pipeline.FILER_CATEGORIES)


# =============================================================================
# Data notification
# =============================================================================

NOTIFICATION_TEMPLATES = {
    "individuals": "DATA_PROTECTION_NOTIFICATION_Individual.docx",
    "active": "DATA_PROTECTION_NOTIFICATION_Active.docx",
    "controlling": "DATA_PROTECTION_NOTIFICATION_Controlling.docx",
    "passive": "DATA_PROTECTION_NOTIFICATION_Passive-CP.docx",
}


def fatca_notifications_service(xml_content: str, categories: dict[str, bool]) -> tuple[bytes, int, int]:
    """The GDPR notification letters owed to each reported account holder.

    One letter per holder, written from the approved templates and returned
    as a ZIP. The letters are built in a temporary directory that is removed
    afterwards: they carry the personal data of real account holders, so
    nothing is left behind on the server once the archive is handed over.

    PDF conversion needs a local MS Word; where it is unavailable the letter
    is still produced as .docx, which is why the two counts are returned
    separately rather than assumed equal.
    """
    reference = RESOURCES_DIR / "reference"
    missing = [name for name in NOTIFICATION_TEMPLATES.values() if not (reference / name).exists()]
    if missing:
        raise LookupError(f"Notification template(s) not bundled: {', '.join(missing)}.")

    with tempfile.TemporaryDirectory() as workspace:
        notifications.generate_notifications(
            xml_content,
            str(reference / NOTIFICATION_TEMPLATES["individuals"]),
            str(reference / NOTIFICATION_TEMPLATES["active"]),
            str(reference / NOTIFICATION_TEMPLATES["controlling"]),
            str(reference / NOTIFICATION_TEMPLATES["passive"]),
            workspace,
            bool(categories.get("individuals", True)), bool(categories.get("active", True)),
            bool(categories.get("controlling", True)), bool(categories.get("passive", True)),
        )
        root = Path(workspace)
        letters = sorted(root.rglob("*.docx"))
        pdfs = sorted(root.rglob("*.pdf"))
        if not letters:
            return b"", 0, 0

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in letters + pdfs:
                archive.write(path, path.relative_to(root).as_posix())
        return buffer.getvalue(), len(letters), len(pdfs)
