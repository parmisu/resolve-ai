from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api import dependencies
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import Customer, Ticket, User
from app.models.enums import TicketStatus, UserRole


@pytest.fixture
def api(monkeypatch):
    settings = get_settings()
    test_url = settings.database_url.set(database="resolve_ai_test")
    test_engine = create_engine(test_url, pool_pre_ping=True)

    test_settings = settings.model_copy(
        update={
            "app_env": "development",
            "dev_api_tokens": {
                "test:alex": SecretStr("test-alex-token"),
                "test:sam": SecretStr("test-sam-token"),
                "test:staff": SecretStr("test-staff-token"),
                "test:admin": SecretStr("test-admin-token"),
            },
        }
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with test_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )

        def override_db():
            yield session

        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_db

        try:
            users = {}
            for name, role in [
                ("alex", UserRole.CUSTOMER),
                ("sam", UserRole.CUSTOMER),
                ("staff", UserRole.SUPPORT_AGENT),
                ("admin", UserRole.ADMINISTRATOR),
            ]:
                user = User(auth_subject=f"test:{name}", role=role)
                session.add(user)
                users[name] = user

            session.flush()

            customers = {}
            for name in ("alex", "sam"):
                customer = Customer(
                    user_id=users[name].id,
                    display_name=name.title(),
                    email=f"{name}@example.com",
                )
                session.add(customer)
                customers[name] = customer

            session.flush()

            open_ticket = Ticket(
                customer_id=customers["alex"].id,
                message="How do I invite a teammate?",
            )
            resolved_ticket = Ticket(
                customer_id=customers["alex"].id,
                message="The loading issue has been resolved.",
                status=TicketStatus.RESOLVED,
                resolved_at=datetime.now(timezone.utc),
            )
            other_ticket = Ticket(
                customer_id=customers["sam"].id,
                message="Which plan am I using?",
            )
            session.add_all([open_ticket, resolved_ticket, other_ticket])
            session.commit()

            with TestClient(app) as client:
                yield {
                    "client": client,
                    "session": session,
                    "users": users,
                    "customers": customers,
                    "open": str(open_ticket.id),
                    "resolved": str(resolved_ticket.id),
                    "other": str(other_ticket.id),
                }
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            session.close()
            transaction.rollback()

    test_engine.dispose()


def headers(name="alex"):
    return {"Authorization": f"Bearer test-{name}-token"}


@pytest.mark.parametrize(
    "auth",
    [{}, {"Authorization": "Bearer invalid-test-token"}],
)
def test_authentication_required(api, auth):
    response = api["client"].get("/tickets", headers=auth)
    assert response.status_code == 401


def test_inactive_user_is_rejected(api):
    api["users"]["alex"].is_active = False
    api["session"].commit()

    response = api["client"].get("/tickets", headers=headers())
    assert response.status_code == 401


def test_create_ticket_uses_authenticated_customer(api):
    response = api["client"].post(
        "/tickets",
        headers=headers(),
        json={"message": "  How do I create a project?  "},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "How do I create a project?"
    assert body["status"] == "open"
    assert body["version"] == 1

    ticket = api["session"].scalar(
        select(Ticket).where(Ticket.message == body["message"])
    )
    assert ticket.customer_id == api["customers"]["alex"].id


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "   "},
        {"message": "Hello", "customer_id": str(uuid4())},
        {"message": "Hello", "status": "closed"},
    ],
)
def test_invalid_create_requests_are_rejected(api, payload):
    response = api["client"].post("/tickets", headers=headers(), json=payload)
    assert response.status_code == 422


def test_customer_list_is_scoped(api):
    response = api["client"].get("/tickets", headers=headers())
    assert response.status_code == 200
    ids = {ticket["id"] for ticket in response.json()}
    assert ids == {api["open"], api["resolved"]}


def test_filters_and_pagination(api):
    response = api["client"].get(
        "/tickets",
        headers=headers(),
        params={"status": "resolved", "limit": 1, "offset": 0},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [api["resolved"]]

    response = api["client"].get(
        "/tickets",
        headers=headers(),
        params={"status": "resolved", "limit": 1, "offset": 1},
    )
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"offset": -1}, {"status": "not-a-status"}],
)
def test_invalid_list_parameters(api, params):
    response = api["client"].get("/tickets", headers=headers(), params=params)
    assert response.status_code == 422


def test_detail_and_cross_customer_access(api):
    client = api["client"]

    response = client.get(f"/tickets/{api['open']}", headers=headers())
    assert response.status_code == 200

    response = client.get(f"/tickets/{api['other']}", headers=headers())
    assert response.status_code == 404

    response = client.patch(
        f"/tickets/{api['other']}",
        headers=headers(),
        json={"version": 1, "message": "Unauthorized change"},
    )
    assert response.status_code == 404


def test_update_and_stale_version(api):
    path = f"/tickets/{api['open']}"
    payload = {"version": 1, "message": "How do I invite two teammates?"}

    response = api["client"].patch(path, headers=headers(), json=payload)
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["message"] == payload["message"]

    response = api["client"].patch(path, headers=headers(), json=payload)
    assert response.status_code == 409

    current = api["client"].get(path, headers=headers()).json()
    assert current["version"] == 2
    assert current["message"] == payload["message"]


def test_customer_cannot_change_priority_or_close(api):
    path = f"/tickets/{api['open']}"

    response = api["client"].patch(
        path,
        headers=headers(),
        json={"version": 1, "priority": "high"},
    )
    assert response.status_code == 403

    response = api["client"].post(
        f"/tickets/{api['resolved']}/close",
        headers=headers(),
        json={"version": 1},
    )
    assert response.status_code == 403


def test_staff_cannot_close_open_ticket(api):
    response = api["client"].post(
        f"/tickets/{api['open']}/close",
        headers=headers("staff"),
        json={"version": 1},
    )
    assert response.status_code == 409


@pytest.mark.parametrize("role", ["staff", "admin"])
def test_staff_can_close_resolved_ticket(api, role):
    path = f"/tickets/{api['resolved']}"

    response = api["client"].post(
        f"{path}/close",
        headers=headers(role),
        json={"version": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["closed_at"] is not None
    assert body["resolved_at"] is not None
    assert body["version"] == 2

    api["session"].expire_all()
    saved = api["client"].get(path, headers=headers(role)).json()
    assert saved["status"] == "closed"

    response = api["client"].post(
        f"{path}/close",
        headers=headers(role),
        json={"version": 2},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 1},
        {"version": 0, "message": "Updated message"},
        {"version": "1", "message": "Updated message"},
        {"version": 1, "message": "   "},
        {"version": 1, "message": None},
        {"version": 1, "status": "resolved"},
    ],
)
def test_invalid_update_requests(api, payload):
    response = api["client"].patch(
        f"/tickets/{api['open']}",
        headers=headers(),
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("payload", [{}, {"version": 0}, {"version": "1"}])
def test_invalid_close_requests(api, payload):
    response = api["client"].post(
        f"/tickets/{api['resolved']}/close",
        headers=headers("staff"),
        json=payload,
    )
    assert response.status_code == 422


def test_staff_can_update_priority(api):
    path = f"/tickets/{api['open']}"
    response = api["client"].patch(
        path,
        headers=headers("staff"),
        json={"version": 1, "priority": "high"},
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2

    api["session"].expire_all()
    ticket = api["session"].scalar(
        select(Ticket).where(
            Ticket.customer_id == api["customers"]["alex"].id,
            Ticket.status == TicketStatus.OPEN,
        )
    )
    assert ticket.priority.value == "high"


def test_staff_cannot_rewrite_customer_message(api):
    response = api["client"].patch(
        f"/tickets/{api['open']}",
        headers=headers("staff"),
        json={"version": 1, "message": "Changed by staff"},
    )
    assert response.status_code == 403


def test_customer_cannot_edit_resolved_ticket(api):
    response = api["client"].patch(
        f"/tickets/{api['resolved']}",
        headers=headers(),
        json={"version": 1, "message": "Changed after resolution"},
    )
    assert response.status_code == 409


def test_close_rejects_stale_version(api):
    response = api["client"].post(
        f"/tickets/{api['resolved']}/close",
        headers=headers("staff"),
        json={"version": 2},
    )
    assert response.status_code == 409
