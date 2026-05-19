from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from halite.audit.writer import record as audit_record
from halite.auth.cookies import CookieCodec
from halite.auth.service import end_session
from halite.auth.service import login as _login
from halite.config import Settings
from halite.db import SessionDep
from halite.deps import CurrentUser, get_codec, get_settings_state

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    display_name: str
    must_change_pw: bool


def _client_meta(request: Request) -> tuple[str, str]:
    ua = request.headers.get("user-agent", "")[:512]
    ip = (request.client.host if request.client else "") or ""
    return ua, ip


@router.post("/login")
async def login_route(
    payload: LoginPayload,
    request: Request,
    response: Response,
    db: SessionDep,
    codec: Annotated[CookieCodec, Depends(get_codec)],
    settings: Annotated[Settings, Depends(get_settings_state)],
) -> UserOut:
    ua, ip = _client_meta(request)
    result = await _login(
        db, payload.username, payload.password, user_agent=ua, ip=ip,
        ttl_minutes=settings.session_ttl_minutes,
    )
    if result is None:
        await audit_record(
            db,
            user_id=None,
            action="auth.login",
            resource=f"user:{payload.username}",
            args_json={"username": payload.username, "password": payload.password},
            salt_jid=None,
            decision="deny",
            result_code=401,
        )
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    await audit_record(
        db,
        user_id=result.user.id,
        action="auth.login",
        resource=f"user:{result.user.username}",
        args_json={"username": result.user.username},
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    response.set_cookie(
        settings.cookie_name,
        codec.sign(result.session_id),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return UserOut(
        username=result.user.username,
        display_name=result.user.display_name,
        must_change_pw=result.user.must_change_pw,
    )


@router.post("/logout", status_code=204)
async def logout_route(
    request: Request,
    db: SessionDep,
    codec: Annotated[CookieCodec, Depends(get_codec)],
    settings: Annotated[Settings, Depends(get_settings_state)],
) -> Response:
    cookie = request.cookies.get(settings.cookie_name)
    if cookie:
        sid = codec.unsign(cookie)
        if sid:
            await end_session(db, sid)
            await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(settings.cookie_name, path="/")
    return response


@router.get("/me")
async def me_route(user: CurrentUser) -> UserOut:
    return UserOut(
        username=user.username,
        display_name=user.display_name,
        must_change_pw=user.must_change_pw,
    )
