"""Request shapes of the PRIIPs KID endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PriipsCalculationRequest(BaseModel):
    fund: dict[str, Any] = Field(description="One fund / share class record of the registry")
    parameters: dict[str, Any] | None = Field(
        default=None, description="An RTS calibration; the configured one when omitted")


class KidRequest(PriipsCalculationRequest):
    template_name: str = Field(default="standard", description="One of GET /priips/templates → available")


class KidRenderRequest(BaseModel):
    kid: dict[str, Any] = Field(description="A KID as POST /priips/kid returned it")


class TemplateTextRequest(BaseModel):
    text: str = Field(description="The whole template, as JSON or YAML text")
    format: Literal["json", "yaml"] = "json"

