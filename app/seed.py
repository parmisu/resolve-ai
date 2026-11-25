from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Customer, Subscription, Ticket, User
from app.models.enums import SubscriptionStatus, UserRole


def seed_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"resolve-ai/demo/{name}")


def main() -> None:
    if get_settings().app_env != "development":
        raise RuntimeError("Demo seed data requires APP_ENV=development.")

    created = 0

    with SessionLocal.begin() as session:
        users = [
            ("customer-alex", UserRole.CUSTOMER),
            ("customer-sam", UserRole.CUSTOMER),
            ("support-agent", UserRole.SUPPORT_AGENT),
            ("administrator", UserRole.ADMINISTRATOR),
        ]

        for name, role in users:
            user_id = seed_id(name)
            if session.get(User, user_id) is None:
                session.add(
                    User(
                        id=user_id,
                        auth_subject=f"synthetic:{name}",
                        role=role,
                    )
                )
                created += 1

        session.flush()

        customers = [
            ("alex", "Alex Morgan", "alex@example.com", "Demo Studio"),
            ("sam", "Sam Taylor", "sam@example.com", "Sample Labs"),
        ]

        for name, display_name, email, company_name in customers:
            customer_id = seed_id(f"profile-{name}")
            if session.get(Customer, customer_id) is None:
                session.add(
                    Customer(
                        id=customer_id,
                        user_id=seed_id(f"customer-{name}"),
                        display_name=display_name,
                        email=email,
                        company_name=company_name,
                    )
                )
                created += 1

        session.flush()

        period_start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 12, 1, tzinfo=timezone.utc)

        for name, plan in [("alex", "starter"), ("sam", "team")]:
            subscription_id = seed_id(f"subscription-{name}")
            if session.get(Subscription, subscription_id) is None:
                session.add(
                    Subscription(
                        id=subscription_id,
                        customer_id=seed_id(f"profile-{name}"),
                        plan_code=plan,
                        status=SubscriptionStatus.ACTIVE,
                        current_period_start=period_start,
                        current_period_end=period_end,
                        cancel_at_period_end=False,
                    )
                )
                created += 1

        tickets = [
            (
                "invite-member",
                "alex",
                "How do I invite a teammate to my TaskFlow project?",
            ),
            (
                "subscription-question",
                "sam",
                "Which subscription plan is my account currently on?",
            ),
            (
                "loading-problem",
                "alex",
                "My project page keeps loading and never opens. "
                "What information should I provide to investigate?",
            ),
        ]

        for name, customer, message in tickets:
            ticket_id = seed_id(f"ticket-{name}")
            if session.get(Ticket, ticket_id) is None:
                session.add(
                    Ticket(
                        id=ticket_id,
                        customer_id=seed_id(f"profile-{customer}"),
                        message=message,
                    )
                )
                created += 1

    print(f"Demo seed complete: {created} records created.")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
