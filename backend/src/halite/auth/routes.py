from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from halite.audit.writer import record as audit_record
from halite.auth.cookies import CookieCodec
from halite.auth.password import hash_password as _hash_password
from halite.auth.password import verify_password as _verify_password
from halite.auth.permissions_cache import load_permissions_for
from halite.auth.service import create_session
from halite.auth.service import _find_user_by_username  # noqa: PLC2701
from halite.auth.service import end_session, end_sessions_for_user
from halite.auth.service import login as _login
from halite.config import Settings
from halite.db import SessionDep
from halite.deps import CurrentUser, get_codec, get_settings_state

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


class PermissionPair(BaseModel):
    verb: str
    resource_glob: str


class UserOut(BaseModel):
    username: str
    display_name: str
    must_change_pw: bool
    permissions: list[PermissionPair] = []


def _perms_of(user) -> list[PermissionPair]:
    return [PermissionPair(verb=v, resource_glob=g) for v, g in getattr(user, "permissions_cache", [])]


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
    result.user.permissions_cache = await load_permissions_for(db, result.user)
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
        permissions=_perms_of(result.user),
    )


@router.post("/demo-login")
async def demo_login_route(
    request: Request,
    response: Response,
    db: SessionDep,
    codec: Annotated[CookieCodec, Depends(get_codec)],
    settings: Annotated[Settings, Depends(get_settings_state)],
) -> UserOut:
    """Passwordless login as the seeded `demo` user. Only available in demo mode."""
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    user = await _find_user_by_username(db, "demo")
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo user not available")
    ua, ip = _client_meta(request)
    sess = await create_session(db, user, user_agent=ua, ip=ip,
                                ttl_minutes=settings.session_ttl_minutes)
    user.permissions_cache = await load_permissions_for(db, user)
    await db.commit()
    response.set_cookie(
        settings.cookie_name, codec.sign(sess.id),
        max_age=settings.session_ttl_minutes * 60, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )
    return UserOut(
        username=user.username, display_name=user.display_name,
        must_change_pw=user.must_change_pw, permissions=_perms_of(user),
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
        permissions=_perms_of(user),
    )


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=1024)


@router.post("/change-password", status_code=204)
async def change_password_route(
    payload: ChangePasswordPayload,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
    codec: Annotated[CookieCodec, Depends(get_codec)],
    settings: Annotated[Settings, Depends(get_settings_state)],
):
    if settings.demo_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Disabled in the demo")
    if not _verify_password(actor.password_hash, payload.current_password):
        await audit_record(
            db, user_id=actor.id, action="auth.change_password",
            resource=f"user:{actor.username}",
            args_json={"current_password": payload.current_password, "new_password": payload.new_password},
            salt_jid=None, decision="deny", result_code=403,
        )
        await db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Current password is incorrect")
    actor.password_hash = _hash_password(payload.new_password)
    actor.must_change_pw = False

    # Revoke all OTHER sessions; keep the current one (the caller's).
    current_cookie = request.cookies.get(settings.cookie_name)
    current_sid = codec.unsign(current_cookie) if current_cookie else None
    await end_sessions_for_user(db, actor.id, except_session_id=current_sid)

    await audit_record(
        db, user_id=actor.id, action="auth.change_password",
        resource=f"user:{actor.username}",
        args_json={"current_password": payload.current_password, "new_password": payload.new_password},
        salt_jid=None, decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=204)
