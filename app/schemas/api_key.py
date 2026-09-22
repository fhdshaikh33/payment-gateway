from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyEnvironment(str, Enum):
    TEST = "TEST"
    LIVE = "LIVE"


class ApiKeyGenerateRequest(BaseModel):
    """Request schema for generating or rotating integration API keys."""

    environment: ApiKeyEnvironment = Field(
        ..., description="Target integration environment ('TEST' or 'LIVE')"
    )


class ApiKeyGenerateResponse(BaseModel):
    """Response schema for newly generated API key pair."""

    key_id: str = Field(..., description="Unique Key ID")
    key_secret: str = Field(
        ..., description="Plaintext Key Secret (shown once)"
    )
    environment: ApiKeyEnvironment = Field(
        ..., description="Integration environment"
    )
    is_active: bool = Field(..., description="Active status flag")
    created_at: datetime = Field(..., description="Key creation timestamp")

    model_config = ConfigDict(from_attributes=True)
