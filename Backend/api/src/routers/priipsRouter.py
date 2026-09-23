"""Routes for the PRIIPs key information document.

PRIIPs is not a workbook regime: it works from the fund registry, runs the
RTS calculation chain — the summary risk indicator, the costs and the four
performance scenarios — and renders a document rather than an XML filing. It
also carries its own configuration: the KID narrative template, the RTS
calibration and the organisation's own settings.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Query
from fastapi.responses import Response

from models.commonModel import ApiResponse, fail, ok, server_error
from services import priipsReportingService

priipsRouter = APIRouter(tags=["PRIIPs KID"])


@priipsRouter.get("/parameters", summary="The PRIIPs RTS parameters the calculations use")
def priips_parameters_router():
    try:
        return ok(priipsReportingService.priips_parameters_service())
    except Exception as exc:
        logging.exception("Reading the PRIIPs parameters failed")
        return server_error(f"Could not read the RTS parameters: {exc}")


@priipsRouter.get("/templates", summary="The KID narrative templates")
def priips_templates_router():
    try:
        return ok(priipsReportingService.priips_templates_service())
    except Exception as exc:
        logging.exception("Reading the KID templates failed")
        return server_error(f"Could not read the KID templates: {exc}")


@priipsRouter.post("/calculate", summary="Run the SRI, cost and scenario calculations")
def priips_calculate_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(priipsReportingService.priips_calculate_service(
            payload.get("fund") or {}, payload.get("parameters")))
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not run the calculation on this fund: {exc}")
    except Exception as exc:
        logging.exception("The PRIIPs calculation failed")
        return server_error(f"Could not run the PRIIPs calculation: {exc}")


@priipsRouter.post("/kid", summary="Assemble a KID from a fund and a template")
def priips_kid_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(priipsReportingService.priips_build_kid_service(
            payload.get("fund") or {}, payload.get("parameters"),
            payload.get("template_name", "standard")))
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not assemble a KID for this fund: {exc}")
    except Exception as exc:
        logging.exception("Assembling the KID failed")
        return server_error(f"Could not assemble the KID: {exc}")


@priipsRouter.post("/kid/render", summary="Render a KID as a PDF")
def priips_render_router(payload: dict = Body(default_factory=dict)):
    kid = payload.get("kid") or payload
    try:
        filename, content, media_type = priipsReportingService.priips_render_service(kid)
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not render this KID: {exc}")
    except Exception as exc:
        logging.exception("Rendering the KID failed")
        return server_error(f"Could not render the KID: {exc}")
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@priipsRouter.get("/templates/{template_name}", summary="One KID template as editable text")
def priips_template_text_router(template_name: str,
                                fmt: str = Query(default="json", pattern="^(json|yaml)$")):
    try:
        return ok(priipsReportingService.priips_template_text_service(template_name, fmt))
    except Exception as exc:
        logging.exception("Reading the %s template failed", template_name)
        return server_error(f"Could not read this template: {exc}")


@priipsRouter.put("/templates/{template_name}", summary="Save a KID template")
def priips_save_template_router(template_name: str, payload: dict = Body(default_factory=dict)):
    """The text is parsed before it is written: a template that does not
    parse is rejected here rather than breaking the next generation."""
    try:
        return ok(priipsReportingService.priips_save_template_service(
            template_name, payload.get("text", ""), payload.get("format", "json")))
    except (ValueError, TypeError) as exc:
        return fail(f"This template is not valid: {exc}")
    except Exception as exc:
        logging.exception("Saving the %s template failed", template_name)
        return server_error(f"Could not save this template: {exc}")


@priipsRouter.post("/templates/{template_name}/reset", summary="Restore a template's default")
def priips_reset_template_router(template_name: str):
    try:
        return ok(priipsReportingService.priips_reset_template_service(template_name))
    except Exception as exc:
        logging.exception("Resetting the %s template failed", template_name)
        return server_error(f"Could not reset this template: {exc}")


@priipsRouter.put("/parameters", summary="Save the RTS calibration")
def priips_save_parameters_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(priipsReportingService.priips_save_parameters_service(payload))
    except Exception as exc:
        logging.exception("Saving the RTS parameters failed")
        return server_error(f"Could not save these parameters: {exc}")


@priipsRouter.post("/parameters/reset", summary="Restore the default RTS calibration")
def priips_reset_parameters_router():
    try:
        return ok(priipsReportingService.priips_reset_parameters_service())
    except Exception as exc:
        logging.exception("Resetting the RTS parameters failed")
        return server_error(f"Could not reset the parameters: {exc}")


@priipsRouter.get("/settings", summary="The organisation's own settings")
def priips_settings_router():
    try:
        return ok(priipsReportingService.priips_settings_service())
    except Exception as exc:
        logging.exception("Reading the application settings failed")
        return server_error(f"Could not read the settings: {exc}")


@priipsRouter.put("/settings", summary="Save the organisation's own settings")
def priips_save_settings_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(priipsReportingService.priips_save_settings_service(payload))
    except Exception as exc:
        logging.exception("Saving the application settings failed")
        return server_error(f"Could not save the settings: {exc}")
