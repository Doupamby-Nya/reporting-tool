"""Routes for the PRIIPs key information document.

PRIIPs is not a workbook regime: it works from the fund registry, runs the
RTS calculation chain — the summary risk indicator, the costs and the four
performance scenarios — and renders a document rather than an XML filing. It
also carries its own configuration: the KID narrative template, the RTS
calibration and the organisation's own settings.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import Response

from models.commonModel import ApiResponse, fail, ok, server_error
from models.priipsModel import KidRenderRequest, KidRequest, PriipsCalculationRequest, TemplateTextRequest
from services import priipsReportingService

priipsRouter = APIRouter(tags=["PRIIPs KID"])


@priipsRouter.get("/parameters", summary="The PRIIPs RTS parameters the calculations use", response_model=ApiResponse[dict[str, Any]])
def priips_parameters_router():
    try:
        return ok(priipsReportingService.priips_parameters_service())
    except Exception as exc:
        logging.exception("Reading the PRIIPs parameters failed")
        return server_error(f"Could not read the RTS parameters: {exc}")


@priipsRouter.get("/templates", summary="The KID narrative templates", response_model=ApiResponse[dict[str, Any]])
def priips_templates_router():
    try:
        return ok(priipsReportingService.priips_templates_service())
    except Exception as exc:
        logging.exception("Reading the KID templates failed")
        return server_error(f"Could not read the KID templates: {exc}")


@priipsRouter.post("/calculate", summary="Run the SRI, cost and scenario calculations", response_model=ApiResponse[dict[str, Any]])
def priips_calculate_router(request: PriipsCalculationRequest):
    try:
        return ok(priipsReportingService.priips_calculate_service(request.fund, request.parameters))
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not run the calculation on this fund: {exc}")
    except Exception as exc:
        logging.exception("The PRIIPs calculation failed")
        return server_error(f"Could not run the PRIIPs calculation: {exc}")


@priipsRouter.post("/kid", summary="Assemble a KID from a fund and a template", response_model=ApiResponse[dict[str, Any]])
def priips_kid_router(request: KidRequest):
    try:
        return ok(priipsReportingService.priips_build_kid_service(
            request.fund, request.parameters, request.template_name))
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not assemble a KID for this fund: {exc}")
    except Exception as exc:
        logging.exception("Assembling the KID failed")
        return server_error(f"Could not assemble the KID: {exc}")


@priipsRouter.post("/kid/render", summary="Render a KID as a PDF", response_class=Response,
                   responses={200: {"content": {"application/pdf": {}}}})
def priips_render_router(request: KidRenderRequest):
    try:
        filename, content, media_type = priipsReportingService.priips_render_service(request.kid)
    except (TypeError, ValueError, KeyError) as exc:
        return fail(f"Could not render this KID: {exc}")
    except Exception as exc:
        logging.exception("Rendering the KID failed")
        return server_error(f"Could not render the KID: {exc}")
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@priipsRouter.get("/templates/{template_name}", summary="One KID template as editable text", response_model=ApiResponse[dict[str, Any]])
def priips_template_text_router(template_name: str,
                                fmt: str = Query(default="json", pattern="^(json|yaml)$")):
    try:
        return ok(priipsReportingService.priips_template_text_service(template_name, fmt))
    except Exception as exc:
        logging.exception("Reading the %s template failed", template_name)
        return server_error(f"Could not read this template: {exc}")


@priipsRouter.put("/templates/{template_name}", summary="Save a KID template", response_model=ApiResponse[dict[str, Any]])
def priips_save_template_router(template_name: str, request: TemplateTextRequest):
    """The text is parsed before it is written: a template that does not
    parse is rejected here rather than breaking the next generation."""
    try:
        return ok(priipsReportingService.priips_save_template_service(
            template_name, request.text, request.format))
    except (ValueError, TypeError) as exc:
        return fail(f"This template is not valid: {exc}")
    except Exception as exc:
        logging.exception("Saving the %s template failed", template_name)
        return server_error(f"Could not save this template: {exc}")


@priipsRouter.post("/templates/{template_name}/reset", summary="Restore a template's default", response_model=ApiResponse[dict[str, Any]])
def priips_reset_template_router(template_name: str):
    try:
        return ok(priipsReportingService.priips_reset_template_service(template_name))
    except Exception as exc:
        logging.exception("Resetting the %s template failed", template_name)
        return server_error(f"Could not reset this template: {exc}")


@priipsRouter.put("/parameters", summary="Save the RTS calibration", response_model=ApiResponse[dict[str, Any]])
def priips_save_parameters_router(
        payload: dict[str, Any] = Body(description="The whole calibration, as GET /priips/parameters returns it")):
    try:
        return ok(priipsReportingService.priips_save_parameters_service(payload))
    except Exception as exc:
        logging.exception("Saving the RTS parameters failed")
        return server_error(f"Could not save these parameters: {exc}")


@priipsRouter.post("/parameters/reset", summary="Restore the default RTS calibration", response_model=ApiResponse[dict[str, Any]])
def priips_reset_parameters_router():
    try:
        return ok(priipsReportingService.priips_reset_parameters_service())
    except Exception as exc:
        logging.exception("Resetting the RTS parameters failed")
        return server_error(f"Could not reset the parameters: {exc}")


@priipsRouter.get("/settings", summary="The organisation's own settings", response_model=ApiResponse[dict[str, Any]])
def priips_settings_router():
    try:
        return ok(priipsReportingService.priips_settings_service())
    except Exception as exc:
        logging.exception("Reading the application settings failed")
        return server_error(f"Could not read the settings: {exc}")


@priipsRouter.put("/settings", summary="Save the organisation's own settings", response_model=ApiResponse[dict[str, Any]])
def priips_save_settings_router(
        payload: dict[str, Any] = Body(description="The settings, as GET /priips/settings returns them")):
    try:
        return ok(priipsReportingService.priips_save_settings_service(payload))
    except Exception as exc:
        logging.exception("Saving the application settings failed")
        return server_error(f"Could not save the settings: {exc}")
