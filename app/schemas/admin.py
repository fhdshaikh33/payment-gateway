from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.merchant import KycStatus, LegalEntityType


class MerchantAdminStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


class MerchantMemberSummary(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    role_name: str

    model_config = ConfigDict(from_attributes=True)


class ApiKeySummary(BaseModel):
    key_id: str
    environment: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantAdminSummary(BaseModel):
    merchant_id: UUID
    business_name: str
    legal_entity_type: LegalEntityType
    kyc_status: str
    created_at: datetime
    active_keys_count: int = 0
    total_payments_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MerchantAdminDetail(BaseModel):
    merchant_id: UUID
    business_name: str
    legal_entity_type: LegalEntityType
    kyc_status: str
    created_at: datetime
    members: List[MerchantMemberSummary] = []
    api_keys: List[ApiKeySummary] = []

    model_config = ConfigDict(from_attributes=True)


class UpdateMerchantStatusRequest(BaseModel):
    status: MerchantAdminStatus = Field(..., description="Target status: APPROVED, SUSPENDED, REJECTED, PENDING")
    reason: Optional[str] = Field(None, description="Optional administrative reason notes")


class UpdateKycReviewRequest(BaseModel):
    kyc_status: KycStatus = Field(..., description="KYC evaluation outcome")
    notes: Optional[str] = Field(None, description="Compliance auditor review notes")


class ComponentHealth(BaseModel):
    name: str
    status: str  # HEALTHY, DEGRADED, UNHEALTHY
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class SystemHealthResponse(BaseModel):
    status: str  # HEALTHY, DEGRADED, UNHEALTHY
    timestamp: datetime
    components: List[ComponentHealth]


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
