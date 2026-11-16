"""Request dependencies: the container and role-based authentication (NFR-05)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rag_lab_generator.api.errors import ApiError
from rag_lab_generator.container import Container
from rag_lab_generator.domain.models import User, UserRole
from rag_lab_generator.infrastructure.security import InvalidTokenError

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


ContainerDep = Annotated[Container, Depends(get_container)]


def current_user(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise ApiError(
            401, "UNAUTHORIZED", "A bearer token is required.", headers=_CHALLENGE
        )
    try:
        user_id = container.tokens.verify(credentials.credentials)
    except InvalidTokenError:
        raise ApiError(
            401,
            "UNAUTHORIZED",
            "The token is invalid or has expired.",
            headers=_CHALLENGE,
        ) from None
    user = container.users.get_user(user_id)
    if user is None:
        raise ApiError(
            401,
            "UNAUTHORIZED",
            "The token's user no longer exists.",
            headers=_CHALLENGE,
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ApiError(
                403,
                "FORBIDDEN",
                "Your role does not allow this operation.",
                {"required_roles": sorted(str(role) for role in allowed)},
            )
        return user

    return check


CourseMaintainer = Annotated[
    User, Depends(require_roles(UserRole.INSTRUCTOR, UserRole.ADMINISTRATOR))
]
RetrievalUser = Annotated[
    User,
    Depends(
        require_roles(UserRole.INSTRUCTOR, UserRole.RESEARCHER, UserRole.ADMINISTRATOR)
    ),
]
