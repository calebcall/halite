from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.service import lookup_session
from halite.db import SessionDep


def get_codec(request: Request) -> CookieCodec:
    codec = getattr(request.app.state, "cookie_codec", None)
    if codec is None:
        raise RuntimeError("CookieCodec not configured on app.state")
    return codec


def get_settings_state(request: Request):
    return request.app.state.settings


async def current_user(
    request: Request,
    db: SessionDep,
    codec: Annotated[CookieCodec, Depends(get_codec)],
    settings = Depends(get_settings_state),
) -> User:
    cookie_value = request.cookies.get(settings.cookie_name)
    if cookie_value is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    session_id = codec.unsign(cookie_value)
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = await lookup_session(db, session_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
