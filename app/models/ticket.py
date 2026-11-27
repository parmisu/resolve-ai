from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TicketCategory, TicketPriority, TicketStatus


class Ticket(Base):
    __tablename__ = "tickets"

    __table_args__ = (
        CheckConstraint(
            "message ~ '[^[:space:]]'",
            name="ck_tickets_message_not_blank",
        ),
        CheckConstraint(
            "NOT mandatory_escalation OR "
            "(escalation_reason IS NOT NULL "
            "AND escalation_reason ~ '[^[:space:]]')",
            name="ck_tickets_escalation_reason_required",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_tickets_positive_version",
        ),
        Index(
            "ix_tickets_customer_created",
            "customer_id",
            "created_at",
        ),
        Index(
            "ix_tickets_queue",
            "status",
            "priority",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    assigned_agent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[TicketCategory | None] = mapped_column(
        Enum(
            TicketCategory,
            name="ticket_category",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
    )

    priority: Mapped[TicketPriority | None] = mapped_column(
        Enum(
            TicketPriority,
            name="ticket_priority",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
    )

    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        nullable=False,
    )

    mandatory_escalation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )

    escalation_reason: Mapped[str | None] = mapped_column(Text)

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    __mapper_args__ = {"version_id_col": version}
