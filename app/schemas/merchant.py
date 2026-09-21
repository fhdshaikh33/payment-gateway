from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LegalEntityType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    PVT_LTD = "PVT_LTD"
    LLP = "LLP"


class KycStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MerchantRegisterRequest(BaseModel):
    """Schema for merchant registration request payload."""

    business_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Name of the business entity",
    )
    legal_entity_type: LegalEntityType = Field(
        ..., description="Type of legal entity (INDIVIDUAL, PVT_LTD, LLP)"
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of primary merchant administrator",
    )
    email: EmailStr = Field(
        ..., description="Email address for primary account login"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password for primary account (min 8 characters)",
    )


class MerchantRegisterResponse(BaseModel):
    """Schema for merchant registration response data payload."""

    merchant_id: UUID
    business_name: str
    legal_entity_type: LegalEntityType
    kyc_status: KycStatus
    user_id: UUID
    full_name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
