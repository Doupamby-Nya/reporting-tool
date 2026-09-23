"""Request shape of the fund registry endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FundsRequest(BaseModel):
    funds: list[dict[str, Any]] = Field(description="Registry records, as POST /funds/parse returned them")
