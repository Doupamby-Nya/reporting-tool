"""Request shape of the AIFMD Annex IV endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class AifmdRequest(BaseModel):
    """The draft the capture form saves: the AIFM-level answers, the AIF-level
    answers and the reporting period.

    The two info blocks stay free-form here on purpose: they carry some two
    hundred ESMA fields whose names and shapes the engine's
    ``submission_from_dicts`` already owns, and whose checks are the CSSF
    controls — duplicating them in a Pydantic model would be a second list to
    keep in step with the first.
    """

    aifm_info: dict[str, Any] = Field(default_factory=dict, description="DATMAN answers, keyed as the form saves them")
    aif_info: dict[str, Any] = Field(default_factory=dict, description="DATAIF answers, keyed as the form saves them")
    period_start: date | None = Field(default=None, description="First day of the reporting period")
    period_end: date | None = Field(default=None, description="Last day of the reporting period")

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
