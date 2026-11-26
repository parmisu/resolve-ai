from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Development token configured in DEV_API_TOKENS.",
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> User:
    settings = get_settings()

    if settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured for this environment.",
        )

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    auth_subject = None
    supplied_token = credentials.credentials.encode("utf-8")

    for subject, configured_token in settings.dev_api_tokens.items():
        expected_token = configured_token.get_secret_value().encode("utf-8")

        if expected_token and compare_digest(supplied_token, expected_token):
            auth_subject = subject
            break

    if auth_subject is None:
        raise unauthorized

    user = db.scalar(
        select(User).where(
            User.auth_subject == auth_subject,
            User.is_active.is_(True),
        )
    )

    if user is None:
        raise unauthorized

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
