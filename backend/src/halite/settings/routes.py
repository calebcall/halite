from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from sqlalchemy import select

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.salt.client import SaltAPIClient
from halite.settings.models import AppSettings
from halite.settings.schemas import (
    LoggingSettingsIn,
    PollerSettingsIn,
    SaltSettingsIn,
    SettingsOut,
    SettingsStatusOut,
    TestSaltConnectionIn,
    TestSaltConnectionOut,
    WidgetSettingsIn,
)
from halite.settings.service import (
    decrypt_salt_password,
    get_settings,
    get_settings_status,
    update_logging,
    update_pollers,
    update_salt,
    update_widget,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/settings", tags=["settings"])


# Status is readable by any logged-in user — the setup-wizard guard needs
# it before /admin/settings is loaded.
@router.get("/status", response_model=SettingsStatusOut)
async def status_route(db: SessionDep, _: CurrentUser) -> SettingsStatusOut:
    return await get_settings_status(db)


@router.get(
    "",
    response_model=SettingsOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def get_route(db: SessionDep, _: CurrentUser) -> SettingsOut:
    return await get_settings(db)


def _redact_password_in_payload(payload: dict) -> dict:
    return {k: ("<redacted>" if k == "password" else v) for k, v in payload.items()}


@router.put(
    "/salt",
    response_model=SettingsOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def put_salt_route(
    body: SaltSettingsIn, request: Request, db: SessionDep, actor: CurrentUser
) -> SettingsOut:
    actor_id = actor.id
    cookie_secret = request.app.state.settings.cookie_secret
    await update_salt(db, body, cookie_secret=cookie_secret)
    await audit_record(
        db,
        user_id=actor_id,
        action="settings.salt.update",
        resource="settings:salt",
        args_json=_redact_password_in_payload(body.model_dump(mode="json", exclude_unset=True)),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    # Hot-reload (re-build salt client + restart schedulers if needed)
    await request.app.state.runtime.reload(db)
    return await get_settings(db)


@router.put(
    "/pollers",
    response_model=SettingsOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def put_pollers_route(
    body: PollerSettingsIn, request: Request, db: SessionDep, actor: CurrentUser
) -> SettingsOut:
    actor_id = actor.id
    await update_pollers(db, body)
    await audit_record(
        db,
        user_id=actor_id,
        action="settings.pollers.update",
        resource="settings:pollers",
        args_json=body.model_dump(exclude_unset=True),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    await request.app.state.runtime.reload(db)
    return await get_settings(db)


@router.put(
    "/widget",
    response_model=SettingsOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def put_widget_route(
    body: WidgetSettingsIn, request: Request, db: SessionDep, actor: CurrentUser
) -> SettingsOut:
    actor_id = actor.id
    await update_widget(db, body)
    await audit_record(
        db,
        user_id=actor_id,
        action="settings.widget.update",
        resource="settings:widget",
        args_json=body.model_dump(exclude_unset=True),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    # Display-only config; no scheduler/runtime impact, so no runtime.reload.
    return await get_settings(db)


@router.put(
    "/logging",
    response_model=SettingsOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def put_logging_route(
    body: LoggingSettingsIn, request: Request, db: SessionDep, actor: CurrentUser
) -> SettingsOut:
    actor_id = actor.id
    await update_logging(db, body)
    await audit_record(
        db,
        user_id=actor_id,
        action="settings.logging.update",
        resource="settings:logging",
        args_json=body.model_dump(exclude_unset=True),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    # Logging-only change doesn't need salt re-wire. Operator restarts the
    # container to pick up log_format. Future plan can move log re-wiring
    # into RuntimeConfig.
    return await get_settings(db)


@router.post(
    "/test-salt",
    response_model=TestSaltConnectionOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def test_salt_route(
    body: TestSaltConnectionIn,
    _: CurrentUser,
) -> TestSaltConnectionOut:
    """Throwaway client. Validates creds without persisting."""
    client = SaltAPIClient(
        base_url=str(body.url).rstrip("/"),
        username=body.username,
        password=body.password.get_secret_value(),
        verify=body.verify,
        eauth=body.eauth,
    )
    try:
        await client.login()
    except Exception as exc:
        return TestSaltConnectionOut(ok=False, detail=f"auth failed: {exc!s}")
    try:
        ids = await client.list_present_minion_ids()
    except Exception as exc:
        await client.aclose()
        return TestSaltConnectionOut(
            ok=True,
            detail=f"logged in (manage.present failed: {exc!s})",
        )
    await client.aclose()
    return TestSaltConnectionOut(
        ok=True,
        detail="logged in",
        minion_count=len(ids),
    )


@router.post(
    "/test-salt-saved",
    response_model=TestSaltConnectionOut,
    dependencies=[require_perm("edit", "settings:*")],
)
async def test_salt_saved_route(
    request: Request,
    db: SessionDep,
    _: CurrentUser,
) -> TestSaltConnectionOut:
    """Test the credentials currently persisted in the DB. Used by the
    settings page when the operator hasn't re-typed the password — we
    can't roundtrip it through the form (security), but we can still
    validate it server-side."""
    row = (await db.execute(select(AppSettings))).scalar_one_or_none()
    if row is None or not (row.salt_api_url and row.salt_api_username):
        return TestSaltConnectionOut(
            ok=False, detail="No saved salt-api configuration."
        )
    cookie_secret = request.app.state.settings.cookie_secret
    password = decrypt_salt_password(row, cookie_secret=cookie_secret)
    if not password:
        return TestSaltConnectionOut(
            ok=False, detail="No saved salt-api password."
        )
    client = SaltAPIClient(
        base_url=row.salt_api_url.rstrip("/"),
        username=row.salt_api_username,
        password=password,
        verify=row.salt_api_verify,
        eauth=row.salt_api_eauth,
    )
    try:
        await client.login()
    except Exception as exc:
        await client.aclose()
        return TestSaltConnectionOut(ok=False, detail=f"auth failed: {exc!s}")
    try:
        ids = await client.list_present_minion_ids()
    except Exception as exc:
        await client.aclose()
        return TestSaltConnectionOut(
            ok=True,
            detail=f"logged in (manage.present failed: {exc!s})",
        )
    await client.aclose()
    return TestSaltConnectionOut(
        ok=True,
        detail="logged in",
        minion_count=len(ids),
    )
