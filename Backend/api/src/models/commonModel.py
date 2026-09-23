"""Shapes shared by every regulatory reporting endpoint.

The API answers with the envelope the platform already uses elsewhere —
``{"success": true, "result": ...}`` or ``{"success": false, "message": ...}``
— so a client only ever has to branch on ``success``.

The envelope carries the *reason*; the HTTP status carries the *category*.
Both are needed: a browser's network tab, a proxy and a monitoring probe all
read the status and none of them read the body, so a failure answered with
200 is a failure nobody outside the client can see. A refused filing is
therefore 400, an unknown regime or draft 404, and a defect in this service
500 — with the same envelope in the body either way.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """The envelope every route returns."""

    success: bool = True
    result: T | None = None
    message: str | None = None


def ok(result: Any) -> dict[str, Any]:
    return {"success": True, "result": result}


def fail(message: str, status_code: int = 400) -> JSONResponse:
    """A refusal the caller can act on: bad input, a filing that did not pass
    its controls, a name that does not exist. 400 unless told otherwise."""
    return JSONResponse(status_code=status_code,
                        content={"success": False, "message": message})


def not_found(message: str) -> JSONResponse:
    """Nothing here by that name — an unknown regime, report or draft."""
    return fail(message, status_code=404)


def server_error(message: str) -> JSONResponse:
    """This service could not do its job. Distinguished from a refusal so a
    monitoring probe can alert on the one and ignore the other."""
    return fail(message, status_code=500)


class Issue(BaseModel):
    """One validation finding, carrying the regulator's own control code so a
    preparer can look it up in the published rule set."""

    level: str = Field(description="'error' blocks generation, 'warning' does not")
    code: str = Field(description="The regulator's control code, e.g. LED-015, CAF-057, CSSF-046")
    message: str


class ValidationResult(BaseModel):
    """The outcome of the business rules, before anything is generated."""

    valid: bool = Field(description="True when no blocking error was raised")
    errors: list[Issue] = []
    warnings: list[Issue] = []


class SchemaResult(BaseModel):
    """The outcome of validating a generated document against the regulator's
    own XSD — a failure here is a defect of this service, not of the data."""

    available: bool = Field(description="False when lxml is not installed")
    valid: bool
    errors: list[str] = []
    detail: str | None = None


class GeneratedFile(BaseModel):
    """One produced filing, ready to be written to disk by the caller."""

    key: str = Field(description="Identifier of the report or file within its regime")
    label: str
    filename: str = Field(description="The name the regulator's naming convention requires")
    content: str = Field(description="The XML document itself")
    schema_validation: SchemaResult
    record_count: int | None = Field(
        default=None, description="Reporting records in the file; AIFMD requires exactly one")


class GenerationResult(BaseModel):
    """What a generate endpoint returns: either the files, or the reasons why
    they could not be produced."""

    generated: bool
    validation: ValidationResult
    files: list[GeneratedFile] = []


def issues_to_payload(issues: list) -> ValidationResult:
    """Converts the domain layer's Issue objects into the API shape."""
    errors = [Issue(level=i.level, code=i.code, message=i.message) for i in issues if i.level == "error"]
    warnings = [Issue(level=i.level, code=i.code, message=i.message) for i in issues if i.level == "warning"]
    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)
