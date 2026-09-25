"""Request and response shapes of the workbook-driven regimes: U 1.1, O 4.1,
ESEF and SAQ.

A draft is the submission a preparer captured — the fields of the engine's
own submission dataclass. Its model is derived from that dataclass rather
than written out a second time, so a field added to an engine appears in the
OpenAPI page and is validated without anyone remembering to copy it here.

Every field is optional at this level: a draft is allowed to be incomplete
while it is being captured, and the engine's own validation_errors() is what
decides whether it can be filed (the answer then says why not). The model
only refuses what can never be right — a date that is not a date, a number
that is not a number.
"""

from __future__ import annotations

import dataclasses
import typing
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from domain.esef import esef_engine
from domain.o41 import o41_engine
from domain.saq import saq_engine
from domain.urr import urr_engine

_SUBMISSIONS: dict[str, type] = {
    "urr": urr_engine.UrrSubmission,
    "o41": o41_engine.O41Submission,
    "esef": esef_engine.EsefSubmission,
    "saq": saq_engine.SaqSubmission,
}


class _Draft(BaseModel):
    # A client may carry fields of its own (the parser's `errors`, a form's
    # bookkeeping); they are ignored rather than refused.
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_missing(cls, value: Any, info) -> Any:
        """A form sends "" for an empty date or number; that is a field not
        filled in, not an invalid one. Text fields keep their "" — the
        engine's checks report a missing name, not this layer."""
        annotation = cls.model_fields[info.field_name].annotation
        if value == "" and str not in typing.get_args(annotation):
            return None
        return value


def _draft_model(regime_key: str, submission: type) -> type[BaseModel]:
    hints = typing.get_type_hints(submission)
    fields = {
        field.name: (hints[field.name] | None, Field(default=None))
        for field in dataclasses.fields(submission)
    }
    name = f"{regime_key.capitalize()}Draft"
    return create_model(name, __base__=_Draft, __doc__=f"A {regime_key} draft: {submission.__name__}.", **fields)


DRAFT_MODELS: dict[str, type[BaseModel]] = {key: _draft_model(key, cls) for key, cls in _SUBMISSIONS.items()}


def draft_payload(draft: BaseModel) -> dict[str, Any]:
    """The draft as the services take it: JSON types, unfilled fields left
    out so the Streamlit defaults apply."""
    return draft.model_dump(mode="json", exclude_none=True)


class FilingResult(BaseModel):
    """What /generate answers. A submission the engine's checks refuse is an
    answer, not an HTTP error: ``generated`` is False and ``errors`` says why."""

    generated: bool
    errors: list[str] = []
    filename: str | None = None
    label: str | None = None
    media_type: str | None = None
    content: str | None = Field(default=None, description="Text filings: XML, EDIFACT, iXBRL")
    content_base64: str | None = Field(default=None, description="Binary filings: the SAQ workbook, the ESEF ZIP")
