from typing import Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

from app.models.enums import (
    SubscriptionStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    UserRole,
)


class RequestSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(RequestSchema):
    auth_subject: str = Field(min_length=1, max_length=255)
    role: UserRole


class UserRead(ResponseSchema):
    id: UUID
    role: UserRole
    is_active: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CustomerCreate(RequestSchema):
    user_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    company_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


class CustomerRead(ResponseSchema):
    id: UUID
    user_id: UUID
    display_name: str
    email: EmailStr
    company_name: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class SubscriptionCreate(RequestSchema):
    customer_id: UUID
    plan_code: str = Field(min_length=1, max_length=50)
    status: SubscriptionStatus
    current_period_start: AwareDatetime
    current_period_end: AwareDatetime
    cancel_at_period_end: bool = False

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.current_period_end <= self.current_period_start:
            raise ValueError("Subscription end must be after its start.")
        return self


class SubscriptionRead(ResponseSchema):
    id: UUID
    customer_id: UUID
    plan_code: str
    status: SubscriptionStatus
    current_period_start: AwareDatetime
    current_period_end: AwareDatetime
    cancel_at_period_end: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


class TicketCreate(RequestSchema):
    message: str = Field(min_length=1)


class TicketRead(ResponseSchema):
    id: UUID
    message: str
    status: TicketStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
    resolved_at: AwareDatetime | None
    closed_at: AwareDatetime | None
    version: int


class StaffTicketRead(TicketRead):
    customer_id: UUID
    assigned_agent_id: UUID | None
    category: TicketCategory | None
    priority: TicketPriority | None
    mandatory_escalation: bool
    escalation_reason: str | None
    version: int


class TicketUpdate(RequestSchema):
    version: int = Field(ge=1, strict=True)
    message: str | None = Field(default=None, min_length=1)
    priority: TicketPriority | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        editable_fields = self.model_fields_set - {"version"}

        if not editable_fields:
            raise ValueError("Provide at least one field to update.")

        for field_name in editable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")

        return self


class TicketClose(RequestSchema):
    version: int = Field(ge=1, strict=True)
