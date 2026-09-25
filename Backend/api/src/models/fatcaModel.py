"""Request shapes of the FATCA / CRS endpoints.

The return itself is built from an uploaded workbook (multipart), so only the
JSON bodies are modelled here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, RootModel

NOTIFICATION_CATEGORIES = ("individuals", "active", "controlling", "passive")


class PreparersRequest(RootModel[dict[str, dict[str, str]]]):
    """The preparer records, keyed by display name; each record carries the
    depositor contact fields of the AEOI schema (``aeoi_lux:Name``,
    ``aeoi_lux:FirstName``, ``aeoi_lux:EmailPersonal``...)."""


class NotificationsRequest(BaseModel):
    xml: str = Field(description="The generated return the letters are written from")
    categories: dict[str, bool] = Field(
        default_factory=dict,
        description=f"Which holders to write to: {', '.join(NOTIFICATION_CATEGORIES)} (all when omitted)")
