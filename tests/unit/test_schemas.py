from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import CustomerCreate, SubscriptionCreate, TicketCreate


def test_ticket_message_is_trimmed():
    ticket = TicketCreate(message="  I cannot sign in.  ")

    assert ticket.message == "I cannot sign in."


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_blank_ticket_message_is_rejected(message):
    with pytest.raises(ValidationError):
        TicketCreate(message=message)


def test_customer_cannot_supply_ticket_owner():
    with pytest.raises(ValidationError):
        TicketCreate(
            message="I need help.",
            customer_id=uuid4(),
        )


def test_invalid_customer_email_is_rejected():
    with pytest.raises(ValidationError):
        CustomerCreate(
            user_id=uuid4(),
            display_name="Demo Customer",
            email="invalid-email",
        )


def test_valid_subscription_is_accepted():
    subscription = SubscriptionCreate(
        customer_id=uuid4(),
        plan_code="pro",
        status="active",
        current_period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        current_period_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert subscription.plan_code == "pro"


@pytest.mark.parametrize("end_day", [1, 2])
def test_invalid_subscription_period_is_rejected(end_day):
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            customer_id=uuid4(),
            plan_code="pro",
            status="active",
            current_period_start=datetime(2026, 1, 2, tzinfo=timezone.utc),
            current_period_end=datetime(2026, 1, end_day, tzinfo=timezone.utc),
        )


def test_subscription_requires_timezone():
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            customer_id=uuid4(),
            plan_code="pro",
            status="active",
            current_period_start=datetime(2026, 1, 1),
            current_period_end=datetime(2026, 2, 1),
        )
