"""The four regimes driven by a workbook: U 1.1, O 4.1, ESEF and SAQ.

They share one production shape — download a template, fill it offline,
upload it back, check it against the regime's rules, generate the filing —
so they share these handlers. Each regime binds them into a router of its
own (see urrRouter, o41Router, esefRouter, saqRouter), which is what makes
the regime visible in the URL and in the OpenAPI page instead of hiding
behind a path parameter.
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, File, Query, UploadFile
from fastapi.responses import Response

from models.commonModel import ApiResponse, fail, not_found, ok, server_error
from models.filingModel import DRAFT_MODELS, FilingResult, draft_payload
from services import filingsService, formsService, inspectService, rulesService


def build_workbook_router(regime_key: str, label: str) -> APIRouter:
    """A router for one workbook-driven regime.

    This module deliberately does not use ``from __future__ import
    annotations``: the request model depends on the regime, and FastAPI can
    only resolve an annotation that names a closure variable when it is a real
    object rather than a string."""
    router = APIRouter(tags=[label])
    Draft = DRAFT_MODELS[regime_key]

    @router.get("/template", summary="Download a regime's blank workbook")
    def template_route():
        try:
            filename, payload, media_type = filingsService.filing_template_service(regime_key)
        except LookupError as exc:
            return not_found(str(exc))
        except Exception as exc:
            logging.exception("Building the %s template failed", regime_key)
            return server_error(f"Could not build the template: {exc}")
        return Response(content=payload, media_type=media_type,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


    @router.post("/parse", summary="Read a filled-in workbook into a draft",
                 response_model=ApiResponse[dict[str, Any]])
    async def parse_route(file: UploadFile = File(...)):
        try:
            return ok(filingsService.filing_parse_service(regime_key, await file.read()))
        except LookupError as exc:
            return not_found(str(exc))
        except Exception as exc:
            logging.exception("Parsing the %s workbook failed", regime_key)
            return server_error(f"Could not read this workbook: {exc}")


    @router.get("/form", summary="The capture form of a regime", response_model=ApiResponse[dict[str, Any]])
    def form_route():
        """The form as data, derived from the submission dataclass and the
        engine's own label lists — so a field renamed in the engine changes the
        form rather than silently stopping short of the filing."""
        try:
            return ok(formsService.filing_form_service(regime_key))
        except LookupError as exc:
            return not_found(str(exc))
        except Exception as exc:
            logging.exception("Building the %s capture form failed", regime_key)
            return server_error(f"Could not build the capture form: {exc}")


    @router.post("/rules", summary="The mapping catalogue and cross-checks of a regime",
                 response_model=ApiResponse[dict[str, Any]])
    def rules_route(draft: Draft = Body(default_factory=Draft)):
        """The rules-engine view. The submission is posted rather than passed in
        the URL because it is the whole captured draft, and because the catalogue
        reports on it — which fields are filled, which cross-checks fail."""
        try:
            return ok(rulesService.filing_rules_service(regime_key, draft_payload(draft)))
        except LookupError as exc:
            return not_found(str(exc))
        except Exception as exc:
            logging.exception("Building the %s rules catalogue failed", regime_key)
            return server_error(f"Could not build the rules catalogue: {exc}")


    # Only a regime whose output is an XML document can be read back in.
    # O 4.1 produces EDIFACT and SAQ a workbook, so neither gets the route —
    # an endpoint that could only ever refuse is worse than none.
    if regime_key in inspectService.REGIMES:

        @router.post("/inspect", summary="Identify and check a filing produced earlier")
        async def inspect_route(file: UploadFile = File(...)):
            """Reads an existing filing back in. Where the regulator's schema is
            bundled the document is validated against it; where it is not, the
            answer says so rather than reporting the file as valid."""
            try:
                return ok(inspectService.inspect_service(regime_key, await file.read()))
            except LookupError as exc:
                return not_found(str(exc))
            except Exception as exc:
                logging.exception("Inspecting the %s filing failed", regime_key)
                return server_error(f"Could not read this filing: {exc}")

    @router.post("/generate", summary="Build a regime's filing", response_model=ApiResponse[FilingResult])
    def generate_route(draft: Draft = Body(default_factory=Draft),
                                as_package: bool = Query(default=False, description="ESEF only: return the ZIP package")):
        try:
            options = {"as_package": as_package} if regime_key == "esef" else {}
            return ok(filingsService.filing_generate_service(regime_key, draft_payload(draft), **options))
        except LookupError as exc:
            return not_found(str(exc))
        except (TypeError, ValueError) as exc:
            # The submission is wrong, not missing: 400, not 404.
            return fail(f"Could not read this submission: {exc}")
        except Exception as exc:
            logging.exception("Generating the %s filing failed", regime_key)
            return server_error(f"Could not generate this filing: {exc}")


    return router
