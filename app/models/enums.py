from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    SUPPORT_AGENT = "support_agent"
    ADMINISTRATOR = "administrator"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class TicketCategory(StrEnum):
    BILLING_AND_SUBSCRIPTION = "billing_and_subscription"
    ACCOUNT_AND_ACCESS = "account_and_access"
    TECHNICAL_ISSUES = "technical_issues"
    PRODUCT_GUIDANCE = "product_guidance"
    SECURITY = "security"
    OTHER = "other"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(StrEnum):
    OPEN = "open"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FAILED = "failed"
