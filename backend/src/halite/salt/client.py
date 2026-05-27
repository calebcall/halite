# backend/src/halite/salt/client.py
"""
SaltAPIClient — async client for salt-api's rest_cherrypy.

Owns the service-account credential. One shared httpx.AsyncClient.
Lazy login — first call does the auth exchange. An asyncio.Lock guards
concurrent token refresh so N concurrent expired-token requests trigger
exactly one re-login. Retries 5xx with exponential backoff (max 3
attempts). Retries 401 exactly once after re-login.

Convenience helpers:
  - wheel_call(fun, **kwargs)
  - local_call(target, fun, target_type='glob', **kwargs)
  - runner_call(fun, **kwargs)
  - list_connected_minions()  -> dict[minion_id, ip]

A SaltAPIError is raised for non-2xx responses; SaltAPIUnavailable for
network / config errors.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Salt-API token lifetime is typically 12 hours by default. Refresh proactively
# when fewer than this many seconds remain on the token.
_TOKEN_REFRESH_MARGIN_S = 60.0

# Retry budget for transient (5xx / network) failures.
_MAX_RETRIES = 3
_BACKOFF_BASE_S = 0.5
_BACKOFF_MAX_S = 4.0


class SaltAPIError(Exception):
    """Raised for non-2xx responses from salt-api."""

    def __init__(self, status: int, body: Any, message: str | None = None) -> None:
        super().__init__(message or f"salt-api responded {status}")
        self.status = status
        self.body = body


class SaltAPIUnavailable(Exception):
    """Raised when salt-api cannot be reached (network, DNS, TLS)."""


class SaltAPIClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        eauth: str = "pam",
        verify: bool | str = True,
        timeout_s: float = 30.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._eauth = eauth
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            verify=verify,
            timeout=timeout_s,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._login_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def login(self) -> None:
        """Eagerly acquire a salt-api token. Raises SaltAPIError /
        SaltAPIUnavailable on failure. Useful for verifying credentials at
        startup before the first real request."""
        await self._ensure_token(force=True)

    # ---------- low-level ----------

    async def _login(self) -> None:
        """Acquire a fresh token. Caller must hold _login_lock."""
        try:
            resp = await self._client.post(
                "/login",
                json={
                    "username": self._username,
                    "password": self._password,
                    "eauth": self._eauth,
                },
            )
        except httpx.HTTPError as exc:
            raise SaltAPIUnavailable(f"salt-api login failed: {exc!r}") from exc

        if resp.status_code >= 400:
            raise SaltAPIError(resp.status_code, _safe_json(resp), "salt-api login rejected")

        body = resp.json()
        # salt-api returns {return: [{token, expire, start, user, eauth, perms}]}
        record = body["return"][0]
        self._token = record["token"]
        self._token_expires_at = float(record.get("expire", time.time() + 600))
        logger.info(
            "salt-api login ok, token expires in %.0fs",
            self._token_expires_at - time.time(),
        )

    async def _ensure_token(self, force: bool = False) -> str:
        """Return a valid token, logging in if needed. Concurrency-safe."""
        if (
            not force
            and self._token
            and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S
        ):
            return self._token
        async with self._login_lock:
            # Re-check inside the lock — another waiter may have refreshed.
            if (
                not force
                and self._token
                and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S
            ):
                return self._token
            await self._login()
        assert self._token is not None
        return self._token

    async def _request(
        self,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """POST a lowstate to salt-api, with retries on 5xx and one retry on
        401 after re-login.

        Authentication is performed via the X-Auth-Token header against the
        session-aware root endpoint (`/`). The `token` value returned by
        salt-api's `/login` is the CherryPy session id — the real Salt eauth
        token lives inside that session and is looked up server-side when the
        header is present. Passing it inline as a `token` field to `/run`
        (which has sessions disabled) results in
        "Authentication failure of type 'token' occurred" because salt-api's
        token cache has no record of the session id.

        ``timeout`` overrides the client-default per request — useful for
        best-effort calls that the caller wants to fail fast. ``max_retries``
        overrides the global retry count for the same reason.
        """
        token = await self._ensure_token()
        retries = max_retries if max_retries is not None else _MAX_RETRIES
        post_kwargs: dict[str, Any] = {
            "json": [payload],
            "headers": {"X-Auth-Token": token},
        }
        if timeout is not None:
            post_kwargs["timeout"] = timeout

        last_network_exc: Exception | None = None
        last_5xx_status: int | None = None
        last_5xx_body: Any = None
        for attempt in range(retries):
            try:
                resp = await self._client.post("/", **post_kwargs)
            except httpx.HTTPError as exc:
                last_network_exc = exc
                logger.warning("salt-api network error (attempt %d): %r", attempt + 1, exc)
                await _sleep_backoff(attempt)
                continue

            if resp.status_code == 401:
                # Token may be stale — refresh and retry once.
                token = await self._ensure_token(force=True)
                post_kwargs["headers"] = {"X-Auth-Token": token}
                resp = await self._client.post("/", **post_kwargs)
                if resp.status_code == 401:
                    raise SaltAPIError(
                        401, _safe_json(resp), "salt-api auth rejected after refresh"
                    )

            if 500 <= resp.status_code < 600:
                last_5xx_status = resp.status_code
                last_5xx_body = _safe_json(resp)
                logger.warning(
                    "salt-api 5xx (attempt %d, status=%d) for fun=%s: %s",
                    attempt + 1,
                    resp.status_code,
                    payload.get("fun", "<unknown>"),
                    _short_body(last_5xx_body),
                )
                await _sleep_backoff(attempt)
                continue

            if resp.status_code >= 400:
                body = _safe_json(resp)
                logger.warning(
                    "salt-api error %d for payload fun=%s: %s",
                    resp.status_code,
                    payload.get("fun", "<unknown>"),
                    _short_body(body),
                )
                raise SaltAPIError(resp.status_code, body)

            return resp.json()

        # All retries exhausted. If we saw ANY 5xx response, salt-api IS
        # reachable but the master is choking — raise SaltAPIError so the
        # route layer surfaces the salt body via wrap_salt_errors → 502.
        # SaltAPIUnavailable is now reserved for the case where every
        # attempt was a network exception.
        if last_5xx_status is not None:
            raise SaltAPIError(last_5xx_status, last_5xx_body)
        raise SaltAPIUnavailable(
            f"salt-api unreachable after {retries} attempts: {last_network_exc!r}"
        )

    # ---------- helpers ----------

    async def wheel_call(self, fun: str, **kwargs: Any) -> Any:
        body = await self._request({"client": "wheel", "fun": fun, **kwargs})
        # wheel return shape: {"return": [{"data": {"return": <X>, ...}}]}
        return body["return"][0]["data"]["return"]

    async def runner_call(
        self,
        fun: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> Any:
        body = await self._request(
            {"client": "runner", "fun": fun, **kwargs},
            timeout=timeout,
            max_retries=max_retries,
        )
        # runner return shape: {"return": [<X>]}
        return body["return"][0]

    async def local_call(
        self,
        target: str,
        fun: str,
        *,
        target_type: str = "glob",
        arg: list[Any] | None = None,
        kwarg: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "client": "local",
            "tgt": target,
            "tgt_type": target_type,
            "fun": fun,
        }
        if arg is not None:
            payload["arg"] = arg
        if kwarg is not None:
            payload["kwarg"] = kwarg
        body = await self._request(payload)
        # local return shape: {"return": [{<minion_id>: <result>, ...}]}
        return body["return"][0]

    async def list_connected_minions(self) -> dict[str, str]:
        """Returns a dict {minion_id: ip} of currently-connected accepted minions.

        Uses the master's presence detection via ``runner.manage.present`` with
        ``show_ip=True``. There is no ``wheel.minions.connected`` in upstream
        Salt — the wheel package only ships ``config``, ``error``,
        ``file_roots``, ``key``, and ``pillar_roots`` — so callers must go
        through the runner client for this information.

        ``manage.present`` with ``show_ip=True`` returns a sorted list of
        ``(minion_id, ip)`` tuples. JSON serialization through salt-api turns
        those into two-element arrays. We also tolerate the older flat-list
        shape (``["minion-a", "minion-b"]``) and a dict shape for robustness.
        """
        result = await self.runner_call("manage.present", show_ip=True)
        out: dict[str, str] = {}
        if isinstance(result, dict):
            # Some salt versions / wrappers expose {id: ip}.
            return {str(k): str(v) for k, v in result.items()}
        if isinstance(result, list):
            for item in result:
                if isinstance(item, list | tuple) and len(item) >= 2:
                    out[str(item[0])] = str(item[1])
                elif isinstance(item, str):
                    # show_ip=True was ignored or unsupported — fall back to id
                    # only. Status is still computed correctly; IP is unknown.
                    out[item] = ""
        return out

    async def list_present_minion_ids(self) -> set[str]:
        """Returns just the set of minion_ids currently present on the master.

        Uses runner.manage.present WITHOUT show_ip — pure master-side session
        state, no per-minion mine.get round-trip, no minion-pinging. Use this
        when you only need the connectivity set (e.g., the fleet dashboard's
        background refresh) and don't need the IP. Sub-second on a healthy
        master regardless of fleet size.
        """
        result = await self.runner_call("manage.present")
        if isinstance(result, list):
            return {str(item) for item in result if isinstance(item, str)}
        if isinstance(result, dict):
            # Some salt versions wrap as {id: <whatever>}
            return {str(k) for k in result}
        return set()

    async def cache_grains(
        self,
        minion_ids: list[str] | None = None,
        batch_size: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """Returns ``{minion_id: grains_dict}`` from master-cached grains.

        Uses ``runner.cache.grains`` — pure master-side cache read, no minion
        contact. When ``minion_ids`` is None, batches with a wildcard target
        are NOT used (some masters drop the connection on full-fleet payloads
        over ~5 MB); instead the caller should pass an explicit list of
        minion ids. We chunk to ``batch_size`` per call and aggregate.
        """
        if not minion_ids:
            # No-op rather than blow up the master with a wildcard. The
            # caller (refresh_grains) is responsible for supplying the
            # list of minions it cares about.
            return {}

        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(minion_ids), batch_size):
            chunk = minion_ids[i : i + batch_size]
            result = await self.runner_call(
                "cache.grains",
                tgt=",".join(chunk),
                tgt_type="list",
            )
            if not isinstance(result, dict):
                continue
            for mid, g in result.items():
                if isinstance(g, dict):
                    out[str(mid)] = g
        return out

    async def get_network_grains_map(
        self,
        target: str = "*",
        *,
        target_type: str = "glob",
    ) -> dict[str, dict[str, Any]]:
        """Return a per-minion subset of network grains used for IP selection.

        Specifically: ``fqdn_ip4``, ``ip4_gw``, and ``ip4_interfaces``. The
        caller (see ``halite.minions.service._pick_primary_ip``) combines these
        to identify the interface IP that sits on the same subnet as the
        default IPv4 gateway — a more reliable signal than ``fqdn_ip4`` alone,
        which gets polluted on hosts where multiple docker bridges happen to
        reverse-resolve to the FQDN.

        Minions that don't respond are omitted.
        """
        result = await self.local_call(
            target,
            "grains.item",
            target_type=target_type,
            arg=["fqdn_ip4", "ip4_gw", "ip4_interfaces"],
        )
        if not isinstance(result, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for mid, sub in result.items():
            if isinstance(sub, dict):
                out[str(mid)] = sub
        return out

    async def list_minion_keys(self) -> dict[str, list[str]]:
        """Returns the master's view of minion keys, bucketed by state.

        Shape: {
          'minions': [...accepted minion ids...],
          'minions_pre': [...unaccepted...],
          'minions_rejected': [...rejected...],
          'minions_denied': [...denied...],
          'local': [...local salt keys...],
        }
        """
        result = await self.wheel_call("key.list_all")
        if not isinstance(result, dict):
            return {}
        return {str(k): list(v) for k, v in result.items()}

    async def get_minion_grains(self, minion_id: str) -> dict[str, Any] | None:
        """Returns grains for a single minion. None if the minion didn't respond
        (e.g. offline)."""
        result = await self.local_call(minion_id, "grains.items", target_type="glob")
        # local return shape: {<minion_id>: <result>}. Could be missing if minion offline.
        if not isinstance(result, dict):
            return None
        grains = result.get(minion_id)
        if not isinstance(grains, dict):
            return None
        return grains

    async def accept_key(self, minion_id: str) -> None:
        """Accept a minion key. Works regardless of current state — passes
        include_rejected and include_denied so an operator clicking 'Accept'
        on a rejected/denied key gets the expected behavior."""
        await self.wheel_call(
            "key.accept",
            match=minion_id,
            include_rejected=True,
            include_denied=True,
        )

    async def reject_key(self, minion_id: str) -> None:
        """Reject a minion key. include_accepted + include_denied for the same
        reason as accept."""
        await self.wheel_call(
            "key.reject",
            match=minion_id,
            include_accepted=True,
            include_denied=True,
        )

    async def delete_key(self, minion_id: str) -> None:
        """Delete a minion key. Idempotent — salt returns success even for
        non-existent minions."""
        await self.wheel_call("key.delete", match=minion_id)

    async def list_jobs(self, limit: int = 50) -> dict[str, dict[str, Any]]:
        """Return recent jobs from the master's job cache.

        Calls runner.jobs.list_jobs and slices to the most recent `limit` entries
        (ordered by jid descending, since salt jids are timestamp-based and
        sort lexicographically by time).
        """
        result = await self.runner_call("jobs.list_jobs")
        if not isinstance(result, dict):
            return {}
        ordered = sorted(result.keys(), reverse=True)[:limit]
        return {jid: result[jid] for jid in ordered if isinstance(result[jid], dict)}

    async def get_job(self, jid: str) -> dict[str, Any] | None:
        """Return detail for one job. None if the jid is not in the cache."""
        result = await self.runner_call("jobs.list_job", jid=jid)
        if not isinstance(result, dict):
            return None
        if not result.get("Function"):
            return None
        return result

    async def run_local_async(
        self,
        target: str,
        fun: str,
        *,
        target_type: str = "glob",
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fire a salt execution module function asynchronously.

        Returns {jid, minions} on success. Salt-api's local_async client
        responds with the assigned jid and the list of targeted minions
        immediately — results land via the jobs cache as minions reply.

        kwargs are passed via the dedicated `kwarg` key (not inlined at
        the top level) so user-supplied keys can't collide with salt-api
        reserved keys like `client`, `tgt`, `fun`.
        """
        payload: dict[str, Any] = {
            "arg": list(args or []),
            "client": "local_async",
            "fun": fun,
            "kwarg": dict(kwargs or {}),
            "tgt": target,
            "tgt_type": target_type,
        }
        body = await self._request(payload)
        # local_async return shape: {"return": [{jid, minions}]}
        if isinstance(body, dict):
            inner = body.get("return")
            if isinstance(inner, list) and inner:
                first = inner[0]
                if isinstance(first, dict):
                    return first
        return {}

    async def kill_job(self, jid: str) -> None:
        """Signal all minions executing `jid` to abort.

        Uses runner.saltutil.kill_job. Idempotent — salt no-ops if the
        jid is unknown or already complete. Failure surfaces via the
        existing SaltAPIError flow.
        """
        await self.runner_call("saltutil.kill_job", jid=jid)

    async def list_active_jobs(self) -> dict[str, dict[str, Any]]:
        """Return the dict of currently-running jobs (jid → details).

        Calls runner.jobs.active with a short timeout + single attempt
        because this runner iterates every minion that has a pending
        job and waits for replies — on fleets with many offline minions
        the salt-side wait can exceed httpx's default 30s timeout, and
        we'd rather fail fast and treat "active set unknown" as empty
        than make the entire Jobs page hang.
        """
        result = await self.runner_call(
            "jobs.active", timeout=5.0, max_retries=1
        )
        if not isinstance(result, dict):
            return {}
        return result

    async def list_execution_functions(self) -> list[str]:
        """Return the sorted, de-duplicated union of execution function names
        that ANY connected minion knows about.

        Targets ``*`` with ``sys.list_functions``. Salt-api gathers responses
        until the master's ``gather_job_timeout`` (default 10s); the union
        across all responders gives a complete catalog including per-minion
        custom modules. The 1-hour backend cache absorbs the cost of the
        cross-minion call.

        We deliberately do NOT call ``runner.doc.execution`` — that runner
        enumerates docstrings for every execution module on the master's
        filesystem and takes 60-120+ seconds on busy masters, which
        exceeds any reasonable HTTP timeout.

        Returns ``[]`` when no minions respond (autocomplete simply doesn't
        populate that day) — does NOT raise, because "no minions" is a
        soft empty state, not an error.
        """
        result = await self.local_call("*", "sys.list_functions", target_type="glob")
        if not isinstance(result, dict):
            return []
        union: set[str] = set()
        for funs in result.values():
            if isinstance(funs, list):
                for f in funs:
                    if isinstance(f, str):
                        union.add(f)
        return sorted(union)


# ---------- helpers ----------


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _short_body(body: Any, limit: int = 500) -> str:
    """Render body to a short string for log lines."""
    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            v = body.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()[:limit]
        return repr(body)[:limit]
    if isinstance(body, str):
        return body[:limit]
    return repr(body)[:limit]


async def _sleep_backoff(attempt: int) -> None:
    delay = min(_BACKOFF_BASE_S * (2**attempt), _BACKOFF_MAX_S)
    await asyncio.sleep(delay)
