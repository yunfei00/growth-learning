"""Operational API response schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ApiInfoResponse(BaseModel):
    name: str
    version: Literal["v1"]
