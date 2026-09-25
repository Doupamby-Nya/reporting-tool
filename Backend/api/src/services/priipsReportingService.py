"""PRIIPs Key Information Document.

The calculations of the PRIIPs RTS — the summary risk indicator, the costs
and the four performance scenarios — and the rendering of the KID itself as
a PDF or a Word document.
"""

from __future__ import annotations

import base64
from typing import Any

from domain.priips import kid_generator, priips_engine
from domain.shared import templates


def priips_parameters_service() -> dict[str, Any]:
    """The RTS parameters the calculations run against, so a client can show
    which assumptions produced a number."""
    return templates.load_rts_parameters()


def priips_calculate_service(fund: dict[str, Any], parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Runs the full RTS calculation chain for one fund: SRI, costs and
    performance scenarios.

    The parameters are resolved here rather than left to the engine's own
    default, so the answer can state which assumptions produced the figures —
    a KID number is only reviewable alongside the calibration behind it.
    """
    parameters = parameters or templates.load_rts_parameters()
    calculation = priips_engine.run_full_calculation(fund, parameters)
    return {
        "sri": calculation.sri,
        "costs": calculation.costs,
        "scenarios": calculation.scenarios,
        "parameters_used": parameters,
    }


def priips_templates_service() -> dict[str, Any]:
    """The KID narrative templates a preparer can start from."""
    return {"available": templates.list_templates(),
            "standard": templates.load_kid_template("standard")}


def priips_build_kid_service(fund: dict[str, Any], parameters: dict[str, Any] | None = None,
                             template_name: str = "standard") -> dict[str, Any]:
    """Assembles the KID: the calculated figures merged into the narrative
    template, ready to be rendered.

    Without explicit parameters the configured RTS calibration is used, as
    the Streamlit KID step did — not the engine's built-in defaults, which
    would make the KID disagree with the calculation step as soon as the
    calibration is edited."""
    parameters = parameters or templates.load_rts_parameters()
    calculation = priips_engine.run_full_calculation(fund, parameters)
    settings = templates.load_app_settings()
    template = templates.load_kid_template(template_name)
    return kid_generator.build_kid(fund, calculation, template, settings)


def priips_render_service(kid: dict[str, Any]) -> tuple[str, bytes, str]:
    """Renders a KID as the PDF a client receives. Returns (filename, bytes,
    media type)."""
    settings = templates.load_app_settings()
    logo = templates.get_logo_bytes()
    payload = kid_generator.render_kid_pdf(
        kid, settings.get("organisation_name") or "Forvis Mazars Luxembourg", logo[0] if logo else None)
    return _filename(kid, "pdf"), payload, "application/pdf"


def priips_render_base64_service(kid: dict[str, Any]) -> dict[str, Any]:
    """The same rendering, wrapped for a JSON client that wants to hold the
    document in memory before offering it as a download."""
    filename, payload, media_type = priips_render_service(kid)
    return {"filename": filename, "media_type": media_type,
            "content_base64": base64.b64encode(payload).decode("ascii")}


def _filename(kid: dict[str, Any], extension: str) -> str:
    name = str(kid.get("fund_name") or "KID").strip() or "KID"
    isin = str(kid.get("isin") or "").strip()
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    return f"KID_{safe}{'_' + isin if isin else ''}.{extension}"


# =============================================================================
# Configuration
# =============================================================================
# The KID narrative, the RTS calibration and the organisation's own settings
# are all editable without touching code — that is the point of the
# configuration step. Each one validates before it is written, so a malformed
# template cannot take the generator down with it.

def priips_template_text_service(template_name: str = "standard", fmt: str = "json") -> dict[str, Any]:
    """One template as editable text, in the format asked for."""
    return {
        "template_name": template_name, "format": fmt,
        "text": templates.load_kid_template_text(template_name, fmt),
    }


def priips_save_template_service(template_name: str, text: str, fmt: str = "json") -> dict[str, Any]:
    """Validates the text and, if it parses, writes it in both formats so the
    JSON and YAML copies can never disagree."""
    return templates.save_kid_template_from_text(template_name, text, fmt)


def priips_reset_template_service(template_name: str = "standard") -> dict[str, Any]:
    return templates.reset_kid_template(template_name)


def priips_save_parameters_service(parameters: dict[str, Any]) -> dict[str, Any]:
    templates.save_rts_parameters(parameters)
    return templates.load_rts_parameters()


def priips_reset_parameters_service() -> dict[str, Any]:
    return templates.reset_rts_parameters()


def priips_settings_service() -> dict[str, Any]:
    return templates.load_app_settings()


def priips_save_settings_service(settings: dict[str, Any]) -> dict[str, Any]:
    templates.save_app_settings(settings)
    return templates.load_app_settings()
