from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models import Customer, Ticket
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole
from app.schemas import TicketClose, TicketCreate, TicketRead, TicketUpdate

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    responses={
        401: {"description": "Missing or invalid authentication"},
        403: {"description": "Access denied"},
        404: {"description": "Ticket not found"},
    },
)


def get_customer_id(db: DatabaseSession, user_id: UUID) -> UUID:
    customer_id = db.scalar(select(Customer.id).where(Customer.user_id == user_id))
    if customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A customer profile is required.",
        )
    return customer_id


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ticket for the authenticated customer",
)
def create_ticket(
    payload: TicketCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> Ticket:
    if user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can create tickets through this endpoint.",
        )

    ticket = Ticket(
        customer_id=get_customer_id(db, user.id),
        message=payload.message,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get(
    "",
    response_model=list[TicketRead],
    summary="List accessible tickets with filters and pagination",
)
def list_tickets(
    db: DatabaseSession,
    user: CurrentUser,
    ticket_status: Annotated[TicketStatus | None, Query(alias="status")] = None,
    category: TicketCategory | None = None,
    priority: TicketPriority | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Ticket]:
    statement = select(Ticket)

    if user.role == UserRole.CUSTOMER:
        statement = statement.where(Ticket.customer_id == get_customer_id(db, user.id))
    elif user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMINISTRATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    if ticket_status is not None:
        statement = statement.where(Ticket.status == ticket_status)
    if category is not None:
        statement = statement.where(Ticket.category == category)
    if priority is not None:
        statement = statement.where(Ticket.priority == priority)

    statement = (
        statement.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


@router.get(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Get an accessible ticket by ID",
)
def get_ticket(
    ticket_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> Ticket:
    statement = select(Ticket).where(Ticket.id == ticket_id)

    if user.role == UserRole.CUSTOMER:
        statement = statement.where(Ticket.customer_id == get_customer_id(db, user.id))
    elif user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMINISTRATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    ticket = db.scalar(statement)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    return ticket


@router.patch(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Update an accessible ticket",
    responses={
        401: {"description": "Missing or invalid authentication"},
        403: {"description": "Requested change is not permitted"},
        404: {"description": "Ticket not found"},
        409: {"description": "Version conflict or ticket state prevents editing"},
    },
)
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> Ticket:
    ticket = get_ticket(ticket_id=ticket_id, db=db, user=user)
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})

    if user.role == UserRole.CUSTOMER:
        if "priority" in changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers cannot change ticket priority.",
            )
        if ticket.status != TicketStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The message can only be edited while the ticket is open.",
            )
    else:
        if "message" in changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff cannot rewrite a customer's message.",
            )
        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resolved or closed tickets cannot be edited.",
            )

    if ticket.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket changed. Fetch its latest version and try again.",
        )

    for field_name, value in changes.items():
        setattr(ticket, field_name, value)

    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket changed during the update. Fetch it again.",
        ) from None

    db.refresh(ticket)
    return ticket


@router.post(
    "/{ticket_id}/close",
    response_model=TicketRead,
    summary="Close a resolved ticket as a support agent or administrator",
    responses={
        401: {"description": "Missing or invalid authentication"},
        403: {"description": "Only staff can close tickets"},
        404: {"description": "Ticket not found"},
        409: {"description": "Version conflict or ticket is not resolved"},
    },
)
def close_ticket(
    ticket_id: UUID,
    payload: TicketClose,
    db: DatabaseSession,
    user: CurrentUser,
) -> Ticket:
    if user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMINISTRATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff can close tickets.",
        )

    ticket = get_ticket(ticket_id=ticket_id, db=db, user=user)

    if ticket.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket changed. Fetch its latest version and try again.",
        )

    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only resolved tickets can be closed.",
        )

    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket changed during closing. Fetch it again.",
        ) from None

    db.refresh(ticket)
    return ticket
