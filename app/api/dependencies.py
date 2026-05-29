from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.security import hash_api_key
from app.db.models import User
from app.db.repositories import UserRepository
from app.db.session import get_db_session

DbSession = Annotated[Session, Depends(get_db_session)]


def get_current_user(
    session: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if not x_api_key:
        raise APIError(status_code=401, code="UNAUTHENTICATED", message="X-API-Key is required.")

    user = UserRepository(session).get_by_api_key_hash(hash_api_key(x_api_key))
    if user is None:
        raise APIError(status_code=401, code="UNAUTHENTICATED", message="Invalid API key.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
